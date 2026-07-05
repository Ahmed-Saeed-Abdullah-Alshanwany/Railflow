"""
ingestion_service.py
--------------------
Incremental ingestion logic for stops and routes.
"""

import psycopg2
from psycopg2.extras import execute_values

from database import get_db_connection, create_tables, get_cursor, save_cursor
from backend.transitland.extractors.stops_extractor import StopsExtractor
from backend.transitland.extractors.berlin_extractor import BerlinExtractor
from backend.transitland.transformers.route_transformer import RouteTransformer


def _classify_transport(stop_name: str) -> str:
    if stop_name.startswith("S+U"):
        return "interchange"
    if stop_name.startswith("S "):
        return "suburban_rail"
    if stop_name.startswith("U "):
        return "metro"
    return "other"


def _count_rows(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def ingest_stops(operator_id: str, limit: int = 100) -> dict:
    conn = get_db_connection()
    create_tables(conn)

    try:
        last_after, prev_count = get_cursor(conn, "stops")

        extractor = StopsExtractor()
        raw_stops, next_after = extractor.extract(
            operator_onestop_id=operator_id,
            limit=limit,
            after=last_after,
        )

        if not raw_stops:
            return {
                "fetched": 0,
                "total_in_db": _count_rows(conn, "stops"),
                "next_after": None,
                "message": "No new stops returned by the API.",
            }

        rows = []
        for s in raw_stops:
            coords = s.get("geometry", {}).get("coordinates", [None, None])
            lon = coords[0]
            lat = coords[1]
            stop_name = s.get("stop_name", "") or ""
            transport_type = _classify_transport(stop_name)

            rows.append((
                s.get("stop_id"),
                s.get("onestop_id"),
                stop_name,
                lat,
                lon,
                s.get("wheelchair_boarding", 0) or 0,
                transport_type,
                (s.get("place") or {}).get("adm0_name"),
                (s.get("place") or {}).get("adm1_name"),
                s.get("platform_code"),
                s.get("location_type", 0) or 0,
            ))

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO stops
                    (stop_id, onestop_id, stop_name, lat, lon,
                     wheelchair, transport_type, country, state,
                     platform_code, location_type)
                VALUES %s
                ON CONFLICT (stop_id) DO UPDATE SET
                    onestop_id     = EXCLUDED.onestop_id,
                    stop_name      = EXCLUDED.stop_name,
                    lat            = EXCLUDED.lat,
                    lon            = EXCLUDED.lon,
                    wheelchair     = EXCLUDED.wheelchair,
                    transport_type = EXCLUDED.transport_type,
                    country        = EXCLUDED.country,
                    state          = EXCLUDED.state,
                    platform_code  = EXCLUDED.platform_code,
                    location_type  = EXCLUDED.location_type
                """,
                rows,
            )
        conn.commit()

        new_total = _count_rows(conn, "stops")
        save_cursor(conn, "stops", operator_id, next_after, new_total)

        msg = (
            "All stops fetched — no more pages."
            if next_after is None
            else f"Page ingested. Call again to continue (next_after={next_after})."
        )

        return {
            "fetched": len(raw_stops),
            "total_in_db": new_total,
            "next_after": next_after,
            "message": msg,
        }

    finally:
        conn.close()


def ingest_routes(operator_id: str, limit: int = 50) -> dict:
    conn = get_db_connection()
    create_tables(conn)

    try:
        last_after, _ = get_cursor(conn, "routes")

        extractor = BerlinExtractor()
        extractor.OPERATOR_ID = operator_id
        raw_routes, next_after = extractor.extract_routes(
            limit=limit,
            after=last_after,
        )

        if not raw_routes:
            return {
                "fetched": 0,
                "total_in_db": _count_rows(conn, "routes"),
                "next_after": None,
                "message": "No new routes returned by the API.",
            }

        transformer = RouteTransformer()
        cleaned = transformer.transform(raw_routes)

        route_rows = [
            (r["route_id"], r.get("line", ""), r.get("agency", ""))
            for r in cleaned
        ]

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO routes (route_id, line, agency)
                VALUES %s
                ON CONFLICT (route_id) DO UPDATE SET
                    line   = EXCLUDED.line,
                    agency = EXCLUDED.agency
                """,
                route_rows,
            )

        with conn.cursor() as cur:
            for route in cleaned:
                rid = route["route_id"]
                for stop_ref in route.get("stops", []):
                    sid = stop_ref.get("stop_id")
                    if not sid:
                        continue
                    cur.execute(
                        "SELECT 1 FROM stops WHERE stop_id = %s", (sid,)
                    )
                    if cur.fetchone():
                        cur.execute(
                            """
                            INSERT INTO route_stops (route_id, stop_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (rid, sid),
                        )

        conn.commit()

        new_total = _count_rows(conn, "routes")
        save_cursor(conn, "routes", operator_id, next_after, new_total)

        msg = (
            "All routes fetched — no more pages."
            if next_after is None
            else f"Page ingested. Call again to continue (next_after={next_after})."
        )

        return {
            "fetched": len(raw_routes),
            "total_in_db": new_total,
            "next_after": next_after,
            "message": msg,
        }

    finally:
        conn.close()
