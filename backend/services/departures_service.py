"""
departures_service.py
=====================
Provides deterministic, fast search functions for the transit agent.
All functions are optimized to run under 5 seconds.

Functions:
  - get_departures(stop_query, after_time, limit)
      → All departures FROM a station (next N trains, route names, headings)
  - get_connection(from_query, to_query, after_time, limit)
      → Direct + 1-transfer connections between two stations with full details
"""

from database import get_db_connection
from typing import List, Dict, Any, Optional
import datetime


# ── helpers ───────────────────────────────────────────────────────────────────

def _resolve_stop(cur, query: str) -> Optional[Dict]:
    """
    Resolves a stop name or ID to its canonical parent-station record.
    Priority: exact match > prefix match > substring match.
    Within same priority, prefers parent station (location_type=1).
    Returns dict with stop_id, stop_name, parent_station or None if not found.
    """
    # Try exact stop_id first
    cur.execute(
        "SELECT stop_id, stop_name, parent_station, location_type "
        "FROM gtfs.stops WHERE stop_id = %s LIMIT 1",
        (query,)
    )
    row = cur.fetchone()
    if row:
        return {"stop_id": row[0], "stop_name": row[1], "parent_station": row[2]}

    # Fuzzy name search with priority:
    #   0 = exact name match
    #   1 = prefix match
    #   2 = any substring
    # Within same priority, prefer parent station (location_type=1).
    cur.execute("""
        SELECT DISTINCT ON (name_priority, loc_priority)
            stop_id, stop_name, parent_station, location_type,
            CASE
                WHEN lower(stop_name) = lower(%s) THEN 0
                WHEN lower(stop_name) LIKE lower(%s) || '%%' THEN 1
                ELSE 2
            END AS name_priority,
            CASE WHEN location_type = 1 THEN 0 ELSE 1 END AS loc_priority
        FROM gtfs.stops
        WHERE stop_name ILIKE %s
        ORDER BY name_priority ASC, loc_priority ASC, LENGTH(stop_name) ASC
        LIMIT 1
    """, (query, query, f"%{query}%"))
    row = cur.fetchone()
    if row:
        return {"stop_id": row[0], "stop_name": row[1], "parent_station": row[2]}

    return None


def _family_ids(cur, stop_id: str, parent_station) -> List[str]:
    """Returns all stop_ids belonging to the same station family (parent + children)."""
    if parent_station:
        cur.execute(
            "SELECT stop_id FROM gtfs.stops WHERE stop_id = %s OR parent_station = %s",
            (parent_station, parent_station)
        )
    else:
        cur.execute(
            "SELECT stop_id FROM gtfs.stops WHERE stop_id = %s OR parent_station = %s",
            (stop_id, stop_id)
        )
    return [r[0] for r in cur.fetchall()] or [stop_id]


def _active_date(cur) -> str:
    """Returns the last active service date from the calendar."""
    cur.execute("SELECT MAX(end_date) FROM gtfs.calendar")
    row = cur.fetchone()
    return str(row[0]) if row and row[0] else str(datetime.date.today())


# ── public API ────────────────────────────────────────────────────────────────

def get_departures(
    stop_query: str,
    after_time: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Returns the next departures FROM a station (identified by name or stop_id).
    """
    if not after_time:
        after_time = datetime.datetime.now().strftime("%H:%M:%S")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            active_date = _active_date(cur)

            stop = _resolve_stop(cur, stop_query)
            if not stop:
                return {
                    "error": f"Station '{stop_query}' not found. Try a different name.",
                    "departures": []
                }

            stop_ids = _family_ids(cur, stop["stop_id"], stop["parent_station"])

             # Departures: all unique (route, destination, departure_time) combos
            cur.execute("""
                SELECT
                    COALESCE(r.route_short_name, r.route_long_name)  AS route_name,
                    (
                        SELECT s_dest.stop_name 
                        FROM gtfs.stop_times st_dest
                        JOIN gtfs.stops s_dest ON st_dest.stop_id = s_dest.stop_id
                        WHERE st_dest.trip_id = t.trip_id
                        ORDER BY st_dest.stop_sequence DESC
                        LIMIT 1
                    )                                                 AS direction,
                    st.departure_time,
                    s.stop_name                                       AS platform_name,
                    COUNT(*) OVER (
                        PARTITION BY t.route_id
                    )                                                  AS trains_today
                FROM gtfs.stop_times st
                JOIN gtfs.trips      t  ON st.trip_id    = t.trip_id
                JOIN gtfs.routes     r  ON t.route_id    = r.route_id
                JOIN gtfs.calendar   c  ON t.service_id  = c.service_id
                JOIN gtfs.stops      s  ON st.stop_id    = s.stop_id
                WHERE st.stop_id = ANY(%s)
                  AND %s BETWEEN c.start_date AND c.end_date
                  AND st.departure_time >= %s
                ORDER BY st.departure_time ASC
                LIMIT %s
            """, (stop_ids, active_date, after_time, limit))


            rows = cur.fetchall()

            # Count distinct routes serving the station today
            cur.execute("""
                SELECT COUNT(DISTINCT t.route_id)
                FROM gtfs.stop_times st
                JOIN gtfs.trips    t ON st.trip_id   = t.trip_id
                JOIN gtfs.calendar c ON t.service_id = c.service_id
                WHERE st.stop_id = ANY(%s)
                  AND %s BETWEEN c.start_date AND c.end_date
            """, (stop_ids, active_date))
            total_routes = cur.fetchone()[0]

        departures = [
            {
                "route":        row[0],
                "direction":    row[1],
                "departs_at":   row[2],
                "platform":     row[3],
                "trains_today": row[4]
            }
            for row in rows
        ]

        return {
            "station_name":  stop["stop_name"],
            "active_date":   active_date,
            "after_time":    after_time,
            "total_routes":  total_routes,
            "departures":    departures
        }

    finally:
        conn.close()


def get_connection(
    from_query: str,
    to_query: str,
    after_time: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Finds direct AND 1-transfer connections between two stations.
    """
    if not after_time:
        after_time = datetime.datetime.now().strftime("%H:%M:%S")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            active_date = _active_date(cur)

            from_stop = _resolve_stop(cur, from_query)
            if not from_stop:
                return {"error": f"Departure station '{from_query}' not found.", "connections": []}

            to_stop = _resolve_stop(cur, to_query)
            if not to_stop:
                return {"error": f"Destination station '{to_query}' not found.", "connections": []}

            from_ids = _family_ids(cur, from_stop["stop_id"], from_stop["parent_station"])
            to_ids   = _family_ids(cur, to_stop["stop_id"],   to_stop["parent_station"])

            # Same-station check
            if set(from_ids) & set(to_ids):
                return {
                    "from_station": from_stop["stop_name"],
                    "to_station":   to_stop["stop_name"],
                    "message":      "المحطة المطلوبة هي نفس محطة الانطلاق.",
                    "connections":  []
                }

            # ── 1. Direct connections ─────────────────────────────────────────
            cur.execute("""
                SELECT
                    COALESCE(r.route_short_name, r.route_long_name) AS route_name,
                    t.trip_headsign                                  AS direction,
                    st1.departure_time                               AS departs_at,
                    st2.arrival_time                                 AS arrives_at,
                    s1.stop_name                                     AS from_platform,
                    s2.stop_name                                     AS to_platform,
                    (st2.stop_sequence - st1.stop_sequence)         AS stops_between
                FROM gtfs.stop_times st1
                JOIN gtfs.stop_times st2 ON  st1.trip_id = st2.trip_id
                                         AND st2.stop_sequence > st1.stop_sequence
                JOIN gtfs.trips      t   ON  st1.trip_id  = t.trip_id
                JOIN gtfs.routes     r   ON  t.route_id   = r.route_id
                JOIN gtfs.calendar   c   ON  t.service_id = c.service_id
                JOIN gtfs.stops      s1  ON  st1.stop_id  = s1.stop_id
                JOIN gtfs.stops      s2  ON  st2.stop_id  = s2.stop_id
                WHERE st1.stop_id = ANY(%s)
                  AND st2.stop_id = ANY(%s)
                  AND %s BETWEEN c.start_date AND c.end_date
                  AND st1.departure_time >= %s
                ORDER BY st1.departure_time ASC
                LIMIT %s
            """, (from_ids, to_ids, active_date, after_time, limit))

            direct_rows = cur.fetchall()
            direct_options = [
                {
                    "type":          "direct",
                    "route":         r[0],
                    "direction":     r[1],
                    "departs_at":    r[2],
                    "arrives_at":    r[3],
                    "from_platform": r[4],
                    "to_platform":   r[5],
                    "stops_between": r[6]
                }
                for r in direct_rows
            ]

            # ── 2. 1-transfer connections (if direct results < limit) ─────────
            transfer_options = []
            remaining = limit - len(direct_options)
            if remaining > 0:
                # Legs1: Trips from origin → intermediate stop
                cur.execute("""
                    SELECT
                        st1.trip_id,
                        st1.departure_time,
                        st_mid.stop_id,
                        COALESCE(s_mid.parent_station, st_mid.stop_id) AS transfer_station,
                        st_mid.arrival_time,
                        COALESCE(r1.route_short_name, r1.route_long_name)
                    FROM gtfs.stop_times st1
                    JOIN gtfs.stop_times st_mid ON  st1.trip_id       = st_mid.trip_id
                                                AND st_mid.stop_sequence > st1.stop_sequence
                    JOIN gtfs.stops      s_mid  ON  st_mid.stop_id    = s_mid.stop_id
                    JOIN gtfs.trips      t1     ON  st1.trip_id       = t1.trip_id
                    JOIN gtfs.routes     r1     ON  t1.route_id       = r1.route_id
                    JOIN gtfs.calendar   c1     ON  t1.service_id     = c1.service_id
                    WHERE st1.stop_id = ANY(%s)
                      AND %s BETWEEN c1.start_date AND c1.end_date
                      AND st1.departure_time >= %s
                    ORDER BY st1.departure_time ASC
                    LIMIT 400
                """, (from_ids, active_date, after_time))
                legs1 = cur.fetchall()

                if legs1:
                    # Get parent transfer stations
                    transfer_stations = list({r[3] for r in legs1})

                    # Get all platforms for these transfer stations
                    cur.execute("""
                        SELECT stop_id, COALESCE(parent_station, stop_id)
                        FROM gtfs.stops
                        WHERE parent_station = ANY(%s) OR stop_id = ANY(%s)
                    """, (transfer_stations, transfer_stations))
                    stop_to_parent = {r[0]: r[1] for r in cur.fetchall()}
                    transfer_stop_ids = list(stop_to_parent.keys())

                    # Legs2: Trips from transfer platforms → destination
                    cur.execute("""
                        SELECT
                            st_mid.trip_id,
                            COALESCE(s_mid.parent_station, st_mid.stop_id) AS transfer_station,
                            st_mid.departure_time,
                            st2.arrival_time,
                            COALESCE(r2.route_short_name, r2.route_long_name),
                            st_mid.stop_id
                        FROM gtfs.stop_times st_mid
                        JOIN gtfs.stops      s_mid  ON  st_mid.stop_id      = s_mid.stop_id
                        JOIN gtfs.stop_times st2    ON  st_mid.trip_id      = st2.trip_id
                                                    AND st2.stop_sequence   > st_mid.stop_sequence
                        JOIN gtfs.trips      t2     ON  st_mid.trip_id      = t2.trip_id
                        JOIN gtfs.routes     r2     ON  t2.route_id         = r2.route_id
                        JOIN gtfs.calendar   c2     ON  t2.service_id       = c2.service_id
                        WHERE st_mid.stop_id = ANY(%s)
                          AND st2.stop_id    = ANY(%s)
                          AND %s BETWEEN c2.start_date AND c2.end_date
                          AND st_mid.departure_time >= %s
                        ORDER BY st_mid.departure_time ASC
                        LIMIT 400
                    """, (transfer_stop_ids, to_ids, active_date, after_time))
                    legs2 = cur.fetchall()

                    # Group legs1 and legs2 by parent transfer_station
                    start_by_transfer = {}
                    for r in legs1:
                        t_station = r[3]
                        start_by_transfer.setdefault(t_station, []).append(r)

                    end_by_transfer = {}
                    for r in legs2:
                        t_station = r[1]
                        end_by_transfer.setdefault(t_station, []).append(r)

                    # Intersect parent transfer stations
                    common_transfers = set(start_by_transfer.keys()) & set(end_by_transfer.keys())

                    seen = set()
                    for t_station in common_transfers:
                        starts = start_by_transfer[t_station]
                        ends = end_by_transfer[t_station]
                        for s in starts:
                            for e in ends:
                                arr1 = s[4] # HH:MM:SS (arrival at transfer)
                                dep2 = e[2] # HH:MM:SS (departure from transfer)
                                if dep2 >= arr1:
                                    try:
                                        h1, m1, s1 = map(int, arr1.split(':'))
                                        h2, m2, s2 = map(int, dep2.split(':'))
                                        diff_minutes = (h2 * 60 + m2) - (h1 * 60 + m1)
                                        # Require transfer buffer between 2 and 120 minutes
                                        if 2 <= diff_minutes <= 120:
                                            key = (s[0], e[0]) # (trip1_id, trip2_id)
                                            if key not in seen:
                                                seen.add(key)
                                                transfer_options.append({
                                                    "type":               "1-transfer",
                                                    "route":              f"{s[5]} ➔ {e[4]}",
                                                    "departs_at":         s[1],
                                                    "arrives_at":         e[3],
                                                    "from_platform":      s[3],
                                                    "to_platform":        e[5],
                                                    "transfer_stop_id":   t_station,
                                                    "transfer_stop_name": "", # resolved below
                                                    "arrives_transfer":   arr1,
                                                    "departs_transfer":   dep2
                                                })
                                    except Exception:
                                        continue

                # Sort transfer options by arrival time, then departure time
                transfer_options.sort(key=lambda x: (x["arrives_at"], x["departs_at"]))
                transfer_options = transfer_options[:remaining]

                # Resolve transfer stop names
                if transfer_options:
                    t_stop_ids = list({o["transfer_stop_id"] for o in transfer_options})
                    cur.execute(
                        "SELECT stop_id, stop_name FROM gtfs.stops WHERE stop_id = ANY(%s)",
                        (t_stop_ids,)
                    )
                    name_map = {r[0]: r[1] for r in cur.fetchall()}
                    for o in transfer_options:
                        o["transfer_stop_name"] = name_map.get(o["transfer_stop_id"], o["transfer_stop_id"])

            all_options = direct_options + transfer_options

        return {
            "from_station":    from_stop["stop_name"],
            "to_station":      to_stop["stop_name"],
            "active_date":     active_date,
            "after_time":      after_time,
            "direct_count":    len(direct_options),
            "transfer_count":  len(transfer_options),
            "connections":     all_options
        }

    finally:
        conn.close()
