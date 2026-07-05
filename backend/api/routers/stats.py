from fastapi import APIRouter, HTTPException
from database import get_db_connection
from typing import Dict, Any, List

router = APIRouter(
    prefix="/api",
    tags=["Statistics"]
)

@router.get("/stats")
def get_stats() -> Dict[str, Any]:
    """
    Queries the database to return live general transit statistics, 
    top stations, top routes, and hourly traffic distribution.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Get the latest release/operation date
            cur.execute("SELECT MAX(end_date) FROM gtfs.calendar;")
            row = cur.fetchone()
            latest_date = str(row[0]) if row and row[0] else None

            if not latest_date:
                raise HTTPException(status_code=404, detail="No transit schedule data found in database.")

            # 2. Get total scheduled trips on this day
            cur.execute("""
                SELECT COUNT(*) 
                FROM gtfs.trips t 
                JOIN gtfs.calendar c ON t.service_id = c.service_id 
                WHERE c.end_date = %s;
            """, (latest_date,))
            total_trips = cur.fetchone()[0]

            # 3. Get top 5 busiest stations
            cur.execute("""
                SELECT s.stop_name, COUNT(*) as num_trips 
                FROM gtfs.stop_times st 
                JOIN gtfs.stops s ON st.stop_id = s.stop_id 
                JOIN gtfs.trips t ON st.trip_id = t.trip_id 
                JOIN gtfs.calendar c ON t.service_id = c.service_id 
                WHERE c.end_date = %s 
                GROUP BY s.stop_name 
                ORDER BY num_trips DESC 
                LIMIT 5;
            """, (latest_date,))
            top_stations = [{"name": r[0], "trips": r[1]} for r in cur.fetchall()]

            busiest_station = top_stations[0]["name"] if top_stations else "Unknown"

            # 4. Get top 5 routes / lines
            cur.execute("""
                SELECT r.route_short_name, COUNT(*) as num_trips 
                FROM gtfs.trips t 
                JOIN gtfs.routes r ON t.route_id = r.route_id 
                JOIN gtfs.calendar c ON t.service_id = c.service_id 
                WHERE c.end_date = %s 
                GROUP BY r.route_short_name 
                ORDER BY num_trips DESC 
                LIMIT 5;
            """, (latest_date,))
            top_routes = [{"name": r[0] or "Unknown Line", "trips": r[1]} for r in cur.fetchall()]

            # 5. Get hourly departures distribution for peak hours chart
            cur.execute("""
                SELECT SUBSTRING(st.departure_time FROM 1 FOR 2) as dep_hour, COUNT(*) as num_departures 
                FROM gtfs.stop_times st 
                JOIN gtfs.trips t ON st.trip_id = t.trip_id 
                JOIN gtfs.calendar c ON t.service_id = c.service_id 
                WHERE c.end_date = %s 
                  AND st.departure_time IS NOT NULL 
                  AND LENGTH(st.departure_time) >= 2
                GROUP BY dep_hour 
                ORDER BY dep_hour ASC;
            """, (latest_date,))
            hourly_data = [{"hour": f"{r[0]}:00", "trips": r[1]} for r in cur.fetchall() if r[0].isdigit()]

        return {
            "general": {
                "total_trips": total_trips,
                "busiest_station": busiest_station,
                "last_update": latest_date
            },
            "top_stations": top_stations,
            "top_routes": top_routes,
            "peak_hours": hourly_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation failed: {str(e)}")
    finally:
        conn.close()
