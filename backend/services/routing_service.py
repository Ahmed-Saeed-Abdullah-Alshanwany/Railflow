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
    with conn.cursor() as cur:
        # Note: We enforce a minimum 2-minute buffer for the transfer to be realistic.
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
                st1.trip_id AS trip1_id,
                COALESCE(r1.route_short_name, r1.route_long_name) AS route1_name,
                st1.departure_time AS start_time,
                st_trans1.arrival_time AS trans1_time,
                st_trans1.stop_id AS transfer_stop_id,
                s_trans.stop_name AS transfer_stop_name,
                st_trans2.departure_time AS trans2_time,
                st2.arrival_time AS end_time,
                st2.trip_id AS trip2_id,
                COALESCE(r2.route_short_name, r2.route_long_name) AS route2_name,
                s1.stop_name AS from_stop_name,
                s2.stop_name AS to_stop_name
            FROM gtfs.stop_times st1
            JOIN gtfs.stop_times st_trans1 ON st1.trip_id = st_trans1.trip_id AND st1.stop_sequence < st_trans1.stop_sequence
            JOIN gtfs.trips t1 ON st1.trip_id = t1.trip_id
            JOIN gtfs.routes r1 ON t1.route_id = r1.route_id
            JOIN gtfs.stops s1 ON st1.stop_id = s1.stop_id
            
            -- Transfer connection
            JOIN gtfs.stop_times st_trans2 ON st_trans2.stop_id = st_trans1.stop_id 
              AND st_trans2.departure_time >= st_trans1.arrival_time
              AND st_trans2.departure_time::interval <= st_trans1.arrival_time::interval + '02:00:00'::interval
              
            JOIN gtfs.stop_times st2 ON st_trans2.trip_id = st2.trip_id AND st_trans2.stop_sequence < st2.stop_sequence
            JOIN gtfs.trips t2 ON st_trans2.trip_id = t2.trip_id
            JOIN gtfs.routes r2 ON t2.route_id = r2.route_id
            JOIN gtfs.stops s2 ON st2.stop_id = s2.stop_id
            
            JOIN gtfs.stops s_trans ON s_trans.stop_id = st_trans1.stop_id
            
            WHERE st1.stop_id IN (SELECT stop_id FROM start_stops) 
              AND st2.stop_id IN (SELECT stop_id FROM end_stops) 
              AND st1.departure_time >= %s
              AND st_trans2.departure_time >= st_trans1.arrival_time
            ORDER BY st2.arrival_time ASC, st1.departure_time ASC
            LIMIT %s;
        """, (start_stop_id, start_stop_id, start_stop_id, end_stop_id, end_stop_id, end_stop_id, start_time, limit))
        
        return [
            {
                "trip1_id": r[0],
                "route1_name": r[1],
                "start_time": r[2],
                "trans1_time": r[3],
                "transfer_stop_id": r[4],
                "transfer_stop_name": r[5],
                "trans2_time": r[6],
                "end_time": r[7],
                "trip2_id": r[8],
                "route2_name": r[9]
            }
            for r in cur.fetchall()
        ]
