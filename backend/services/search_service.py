from database import get_db_connection
from typing import List, Dict, Any

def search_stops(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search stops in gtfs.stops using fuzzy text matching.
    Prioritizes prefix matches over general substring matches.
    """
    if not query:
        return []

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Sort exact/prefix matches higher, and also order by name length (shorter names first)
            cur.execute("""
                SELECT stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station, platform_code
                FROM gtfs.stops
                WHERE stop_name ILIKE %s
                ORDER BY 
                    CASE 
                        WHEN stop_name = %s THEN 1
                        WHEN stop_name ILIKE %s THEN 2
                        ELSE 3
                    END,
                    LENGTH(stop_name) ASC,
                    stop_name ASC
                LIMIT %s;
            """, (f"%{query}%", query, f"{query}%", limit))
            
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    "stop_id": r[0],
                    "stop_name": r[1],
                    "stop_lat": r[2],
                    "stop_lon": r[3],
                    "location_type": r[4],
                    "parent_station": r[5],
                    "platform_code": r[6]
                })
            return results
    finally:
        conn.close()
