from database import get_db_connection
from typing import List, Dict, Any, Optional
import datetime

def find_routes(
    start_stop_id: str, 
    end_stop_id: str, 
    start_time_str: Optional[str] = None,
    limit: int = 3
) -> Dict[str, Any]:
    """
    Finds direct and 1-transfer transit routes between two stop IDs departing after start_time_str.
    Time format must be HH:MM:SS (e.g. 09:30:00). Defaults to current local time if not provided.
    """
    if not start_time_str:
        start_time_str = datetime.datetime.now().strftime("%H:%M:%S")

    conn = get_db_connection()
    try:
        # Check and resolve start and end stops (supporting both direct IDs and human-readable names)
        with conn.cursor() as cur:
            # Resolve start stop
            resolved_start = None
            cur.execute("SELECT stop_id FROM gtfs.stops WHERE stop_id = %s OR parent_station = %s LIMIT 1", (start_stop_id, start_stop_id))
            row = cur.fetchone()
            if row:
                resolved_start = start_stop_id
            else:
                cur.execute("""
                    SELECT stop_id FROM gtfs.stops 
                    WHERE stop_name ILIKE %s
                    ORDER BY 
                        CASE 
                            WHEN stop_name = %s THEN 1
                            WHEN stop_name ILIKE %s THEN 2
                            ELSE 3
                        END,
                        LENGTH(stop_name) ASC
                    LIMIT 1
                """, (f"%{start_stop_id}%", start_stop_id, f"{start_stop_id}%"))
                row = cur.fetchone()
                if row:
                    resolved_start = row[0]
            
            if not resolved_start:
                return {"start_stop_id": start_stop_id, "end_stop_id": end_stop_id, "start_time": start_time_str, "options": [], "error": f"Start stop '{start_stop_id}' not found in the database. Please search for the correct name using search_stops."}

            # Resolve end stop
            resolved_end = None
            cur.execute("SELECT stop_id FROM gtfs.stops WHERE stop_id = %s OR parent_station = %s LIMIT 1", (end_stop_id, end_stop_id))
            row = cur.fetchone()
            if row:
                resolved_end = end_stop_id
            else:
                cur.execute("""
                    SELECT stop_id FROM gtfs.stops 
                    WHERE stop_name ILIKE %s
                    ORDER BY 
                        CASE 
                            WHEN stop_name = %s THEN 1
                            WHEN stop_name ILIKE %s THEN 2
                            ELSE 3
                        END,
                        LENGTH(stop_name) ASC
                    LIMIT 1
                """, (f"%{end_stop_id}%", end_stop_id, f"{end_stop_id}%"))
                row = cur.fetchone()
                if row:
                    resolved_end = row[0]

            if not resolved_end:
                return {"start_stop_id": start_stop_id, "end_stop_id": end_stop_id, "start_time": start_time_str, "options": [], "error": f"End stop '{end_stop_id}' not found in the database. Please search for the correct name using search_stops."}

        actual_start = resolved_start
        actual_end = resolved_end

        # Fast-track check: If start and end are the same stop or belong to the same parent station
        with conn.cursor() as cur:
            cur.execute("SELECT parent_station FROM gtfs.stops WHERE stop_id = %s", (actual_start,))
            p1 = cur.fetchone()
            cur.execute("SELECT parent_station FROM gtfs.stops WHERE stop_id = %s", (actual_end,))
            p2 = cur.fetchone()
            
            p1_id = p1[0] if p1 else None
            p2_id = p2[0] if p2 else None

            if actual_start == actual_end or (p1_id and p2_id and p1_id == p2_id):
                return {
                    "start_stop_id": actual_start,
                    "end_stop_id": actual_end,
                    "start_time": start_time_str,
                    "options": [],
                    "message": "المغادرة والوصول في نفس المحطة. أنت بالفعل في وجهتك، لا توجد رحلات مطلوبة."
                }

        routes_found = []
        
        # 1. Search for direct routes
        direct_routes = _find_direct_routes(conn, actual_start, actual_end, start_time_str, limit)
        for route in direct_routes:
            routes_found.append({
                "type": "direct",
                "departure_time": route["start_time"],
                "arrival_time": route["end_time"],
                "legs": [
                    {
                        "trip_id": route["trip_id"],
                        "route_id": route["route_id"],
                        "route_name": route["route_name"],
                        "from_stop_id": actual_start,
                        "to_stop_id": actual_end,
                        "departure_time": route["start_time"],
                        "arrival_time": route["end_time"]
                    }
                ]
            })
            
        # 2. Search for 1-transfer routes if we need more options
        if len(routes_found) < limit:
            transfer_routes = _find_one_transfer_routes(
                conn, actual_start, actual_end, start_time_str, limit - len(routes_found)
            )
            for route in transfer_routes:
                routes_found.append({
                    "type": "1-transfer",
                    "departure_time": route["start_time"],
                    "arrival_time": route["end_time"],
                    "legs": [
                        {
                            "trip_id": route["trip1_id"],
                            "route_name": route["route1_name"],
                            "from_stop_id": actual_start,
                            "to_stop_id": route["transfer_stop_id"],
                            "to_stop_name": route["transfer_stop_name"],
                            "departure_time": route["start_time"],
                            "arrival_time": route["trans1_time"]
                        },
                        {
                            "trip_id": route["trip2_id"],
                            "route_name": route["route2_name"],
                            "from_stop_id": route["transfer_stop_id"],
                            "from_stop_name": route["transfer_stop_name"],
                            "to_stop_id": actual_end,
                            "departure_time": route["trans2_time"],
                            "arrival_time": route["end_time"]
                        }
                    ]
                })

        return {
            "start_stop_id": actual_start,
            "end_stop_id": actual_end,
            "start_time": start_time_str,
            "options": routes_found
        }
    finally:
        conn.close()

def _find_direct_routes(conn, start_stop_id: str, end_stop_id: str, start_time: str, limit: int) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            WITH start_stops AS (
                SELECT stop_id FROM gtfs.stops 
                WHERE stop_id = %s OR parent_station = %s OR parent_station = (
                    SELECT parent_station FROM gtfs.stops WHERE stop_id = %s AND parent_station IS NOT NULL
                )
            ),
            end_stops AS (
                SELECT stop_id FROM gtfs.stops 
                WHERE stop_id = %s OR parent_station = %s OR parent_station = (
                    SELECT parent_station FROM gtfs.stops WHERE stop_id = %s AND parent_station IS NOT NULL
                )
            )
            SELECT 
                st1.trip_id,
                r.route_id,
                COALESCE(r.route_short_name, r.route_long_name) AS route_name,
                st1.departure_time,
                st2.arrival_time,
                s1.stop_name AS from_stop_name,
                s2.stop_name AS to_stop_name
            FROM gtfs.stop_times st1
            JOIN gtfs.stop_times st2 ON st1.trip_id = st2.trip_id AND st1.stop_sequence < st2.stop_sequence
            JOIN gtfs.trips t ON st1.trip_id = t.trip_id
            JOIN gtfs.routes r ON t.route_id = r.route_id
            JOIN gtfs.stops s1 ON st1.stop_id = s1.stop_id
            JOIN gtfs.stops s2 ON st2.stop_id = s2.stop_id
            WHERE st1.stop_id IN (SELECT stop_id FROM start_stops) 
              AND st2.stop_id IN (SELECT stop_id FROM end_stops) 
              AND st1.departure_time >= %s
            ORDER BY st1.departure_time ASC
            LIMIT %s;
        """, (start_stop_id, start_stop_id, start_stop_id, end_stop_id, end_stop_id, end_stop_id, start_time, limit))
        
        return [
            {
                "trip_id": r[0],
                "route_id": r[1],
                "route_name": f"{r[2]} ({r[5]} -> {r[6]})",
                "start_time": r[3],
                "end_time": r[4]
            }
            for r in cur.fetchall()
        ]

def _find_one_transfer_routes(conn, start_stop_id: str, end_stop_id: str, start_time: str, limit: int) -> List[Dict[str, Any]]:
    # 1. Fetch start stops and end stops PIDs
    with conn.cursor() as cur:
        cur.execute("""
            WITH start_stops AS (
                SELECT stop_id FROM gtfs.stops 
                WHERE stop_id = %s OR parent_station = %s OR parent_station = (
                    SELECT parent_station FROM gtfs.stops WHERE stop_id = %s AND parent_station IS NOT NULL
                )
            ) SELECT stop_id FROM start_stops;
        """, (start_stop_id, start_stop_id, start_stop_id))
        start_stop_ids = [r[0] for r in cur.fetchall()]

        cur.execute("""
            WITH end_stops AS (
                SELECT stop_id FROM gtfs.stops 
                WHERE stop_id = %s OR parent_station = %s OR parent_station = (
                    SELECT parent_station FROM gtfs.stops WHERE stop_id = %s AND parent_station IS NOT NULL
                )
            ) SELECT stop_id FROM end_stops;
        """, (end_stop_id, end_stop_id, end_stop_id))
        end_stop_ids = [r[0] for r in cur.fetchall()]

        if not start_stop_ids or not end_stop_ids:
            return []

        # 2. Get all trips passing through start stops, and their subsequent stop times
        cur.execute("""
            SELECT 
                st1.trip_id,
                st1.stop_id AS start_stop_id,
                st1.departure_time AS start_time,
                st_trans.stop_id AS transfer_stop_id,
                st_trans.arrival_time AS transfer_arrival_time,
                COALESCE(r1.route_short_name, r1.route_long_name) AS route_name
            FROM gtfs.stop_times st1
            JOIN gtfs.stop_times st_trans ON st1.trip_id = st_trans.trip_id AND st1.stop_sequence < st_trans.stop_sequence
            JOIN gtfs.trips t1 ON st1.trip_id = t1.trip_id
            JOIN gtfs.routes r1 ON t1.route_id = r1.route_id
            WHERE st1.stop_id = ANY(%s) AND st1.departure_time >= %s;
        """, (start_stop_ids, start_time))
        start_trips = cur.fetchall()

        # 3. Get all trips passing through end stops, and their preceding stop times
        cur.execute("""
            SELECT 
                st2.trip_id,
                st2.stop_id AS end_stop_id,
                st2.arrival_time AS end_time,
                st_trans.stop_id AS transfer_stop_id,
                st_trans.departure_time AS transfer_departure_time,
                COALESCE(r2.route_short_name, r2.route_long_name) AS route_name
            FROM gtfs.stop_times st2
            JOIN gtfs.stop_times st_trans ON st2.trip_id = st_trans.trip_id AND st_trans.stop_sequence < st2.stop_sequence
            JOIN gtfs.trips t2 ON st2.trip_id = t2.trip_id
            JOIN gtfs.routes r2 ON t2.route_id = r2.route_id
            WHERE st2.stop_id = ANY(%s);
        """, (end_stop_ids,))
        end_trips = cur.fetchall()

    # 4. Group by transfer stop
    start_by_transfer = {}
    for r in start_trips:
        trans_stop = r[3]
        if trans_stop not in start_by_transfer:
            start_by_transfer[trans_stop] = []
        start_by_transfer[trans_stop].append(r)

    end_by_transfer = {}
    for r in end_trips:
        trans_stop = r[3]
        if trans_stop not in end_by_transfer:
            end_by_transfer[trans_stop] = []
        end_by_transfer[trans_stop].append(r)

    # 5. Intersect transfer stops and find matches
    common_transfers = set(start_by_transfer.keys()) & set(end_by_transfer.keys())
    
    options = []
    for trans_stop in common_transfers:
        starts = start_by_transfer[trans_stop]
        ends = end_by_transfer[trans_stop]
        
        for s in starts:
            for e in ends:
                arr_time = s[4] # HH:MM:SS
                dep_time = e[4] # HH:MM:SS
                
                if dep_time >= arr_time:
                    try:
                        # parse to minutes to verify 2 hours buffer
                        h1, m1, s1 = map(int, arr_time.split(':'))
                        h2, m2, s2 = map(int, dep_time.split(':'))
                        diff_minutes = (h2 * 60 + m2) - (h1 * 60 + m1)
                        if 0 <= diff_minutes <= 120:
                            options.append({
                                "trip1_id": s[0],
                                "route1_name": s[5],
                                "start_time": s[2],
                                "trans1_time": s[4],
                                "transfer_stop_id": trans_stop,
                                "transfer_stop_name": "", # resolved below
                                "trans2_time": e[4],
                                "end_time": e[2],
                                "trip2_id": e[0],
                                "route2_name": e[5]
                            })
                    except Exception:
                        continue

    # Sort options by end_time, then start_time
    options.sort(key=lambda x: (x["end_time"], x["start_time"]))
    
    # Take limit and resolve transfer stop names
    final_options = options[:limit]
    if final_options:
        with conn.cursor() as cur:
            for opt in final_options:
                cur.execute("SELECT stop_name FROM gtfs.stops WHERE stop_id = %s LIMIT 1", (opt["transfer_stop_id"],))
                row = cur.fetchone()
                if row:
                    opt["transfer_stop_name"] = row[0]
                    
    return final_options
