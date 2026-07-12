from database import get_db_connection
from typing import List, Dict, Any

def search_stops(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search stops in gtfs.stops using fuzzy text matching.
    If the query is empty or a generic keyword, returns a list of main stations.
    Returns DISTINCT station names, preferring the parent-station row (location_type=1)
    over individual platform rows to avoid showing the same name multiple times.
    """
    q_clean = (query or "").strip().lower()
    generic_words = {
        "", "all", "stops", "stations", "station", "list", "show", "any", "everything", "of", "the",
        "محطة", "المحطات", "كل", "محطات", "أي", "عرض", "الموجودة", "الموجوده", "الموجودات", "في", "الشبكة", "الشبكه"
    }
    
    # Split query into words and check if it consists only of generic words
    words = [w for w in q_clean.replace("؟", "").split() if w]
    is_generic = not q_clean or all(w in generic_words for w in words)


    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if is_generic:
                # Returns actual parent stations ordered by popularity (most active first)
                cur.execute("""
                    SELECT 
                        p.stop_id, p.stop_name, p.stop_lat, p.stop_lon,
                        p.location_type, p.parent_station, p.platform_code,
                        COUNT(st.trip_id) as popularity
                    FROM gtfs.stop_times st
                    JOIN gtfs.stops s ON st.stop_id = s.stop_id
                    JOIN gtfs.stops p ON COALESCE(s.parent_station, s.stop_id) = p.stop_id
                    WHERE p.location_type = 1
                    GROUP BY p.stop_id, p.stop_name, p.stop_lat, p.stop_lon, p.location_type, p.parent_station, p.platform_code
                    ORDER BY popularity DESC
                    LIMIT %s;
                """, (limit,))


            else:
                # DISTINCT ON (stop_name) keeps only the first row per unique name.
                # ORDER BY ensures we pick: parent station first (location_type=1),
                # then exact match, then prefix match, then any substring match.
                cur.execute("""
                    SELECT DISTINCT ON (stop_name)
                        stop_id, stop_name, stop_lat, stop_lon,
                        location_type, parent_station, platform_code
                    FROM gtfs.stops
                    WHERE stop_name ILIKE %s
                    ORDER BY
                        stop_name,
                        CASE WHEN location_type = 1 THEN 0 ELSE 1 END,
                        CASE
                            WHEN stop_name = %s          THEN 0
                            WHEN stop_name ILIKE %s       THEN 1
                            ELSE                               2
                        END,
                        LENGTH(stop_name) ASC
                    LIMIT %s;
                """, (f"%{query}%", query, f"{query}%", limit))

            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    "stop_id":        r[0],
                    "stop_name":      r[1],
                    "stop_lat":       r[2],
                    "stop_lon":       r[3],
                    "location_type":  r[4],
                    "parent_station": r[5],
                    "platform_code":  r[6]
                })
            return results
    finally:
        conn.close()


