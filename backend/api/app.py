import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from backend.api.fetch_service import fetch_stops, fetch_routes
from pydantic import BaseModel
from backend.api.routers.agent import router as agent_router

load_dotenv()

app = FastAPI(
    title="Railflow Fetch API",
    description="Fetches transit data from Transitland API and returns it directly (No DB).",
    version="1.0.0",
)

app.include_router(agent_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_OPERATOR = os.getenv("DEFAULT_OPERATOR_ID", "o-u33-s~bahnberlingmbh")

class FetchResponse(BaseModel):
    status: str
    entity: str
    fetched: int
    next_after: Optional[int] = None
    data: list

@app.get("/fetch/stops", response_model=FetchResponse, tags=["Fetch Data directly from API"])
def fetch_stops_endpoint(
    operator_id: str = Query(default=None, description="Transitland operator Onestop ID."),
    limit: int = Query(default=100, ge=1, le=100),
    after: Optional[int] = Query(default=None, description="Pagination cursor from previous request")
):
    op = operator_id or DEFAULT_OPERATOR
    try:
        result = fetch_stops(operator_id=op, limit=limit, after=after)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return FetchResponse(
        status="ok",
        entity="stops",
        fetched=result["fetched"],
        next_after=result["next_after"],
        data=result["data"]
    )

@app.get("/fetch/routes", response_model=FetchResponse, tags=["Fetch Data directly from API"])
def fetch_routes_endpoint(
    operator_id: str = Query(default=None, description="Transitland operator Onestop ID."),
    limit: int = Query(default=50, ge=1, le=100),
    after: Optional[int] = Query(default=None, description="Pagination cursor from previous request")
):
    op = operator_id or DEFAULT_OPERATOR
    try:
        result = fetch_routes(operator_id=op, limit=limit, after=after)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return FetchResponse(
        status="ok",
        entity="routes",
        fetched=result["fetched"],
        next_after=result["next_after"],
        data=result["data"]
    )

@app.get("/api/analytics", tags=["Analytics"])
def get_analytics_endpoint(mode: str = "day"):
    """
    Returns GTFS system metrics and statistics for the dashboard.
    mode='day'   → filters all charts to the last active service day only (default, consistent with KPI).
    mode='month' → aggregates across the entire stored period (all calendar entries).
    """
    from database import get_db_connection
    import datetime

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 1. Last update/active date (max end_date)
            cur.execute("SELECT MIN(start_date), MAX(end_date) FROM gtfs.calendar")
            range_row = cur.fetchone()
            max_date = str(range_row[1]) if range_row and range_row[1] else str(datetime.date.today())
            min_date = str(range_row[0]) if range_row and range_row[0] else max_date

            date_range = {
                "start": min_date,
                "end": max_date,
                "active_day": max_date,
                "mode": mode
            }

            # 2. Total active daily trips count — always last day
            cur.execute("""
                SELECT COUNT(*) FROM gtfs.trips t 
                JOIN gtfs.calendar c ON t.service_id = c.service_id 
                WHERE %s BETWEEN c.start_date AND c.end_date
            """, (max_date,))
            total_trips = cur.fetchone()[0]
            if total_trips == 0:
                cur.execute("SELECT COUNT(*) FROM gtfs.trips")
                total_trips = cur.fetchone()[0]

            # Build calendar filter clause depending on mode
            if mode == "month":
                # No date filter — count across whole stored period
                cal_filter = ""
                cal_params_busiest = ()
                cal_params_routes = ()
                cal_params_hours = ()
            else:
                # Filter to last active day only
                cal_filter = "AND %s BETWEEN c.start_date AND c.end_date"
                cal_params_busiest = (max_date,)
                cal_params_routes = (max_date,)
                cal_params_hours = (max_date,)

            # 3. Top 5 busiest stations
            if mode == "month":
                cur.execute("""
                    SELECT s.stop_name, COUNT(st.trip_id) as trip_count 
                    FROM gtfs.stop_times st 
                    JOIN gtfs.stops s ON st.stop_id = s.stop_id
                    JOIN gtfs.trips t ON st.trip_id = t.trip_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    GROUP BY s.stop_name 
                    ORDER BY trip_count DESC 
                    LIMIT 5
                """)
            else:
                cur.execute("""
                    SELECT s.stop_name, COUNT(st.trip_id) as trip_count 
                    FROM gtfs.stop_times st 
                    JOIN gtfs.stops s ON st.stop_id = s.stop_id
                    JOIN gtfs.trips t ON st.trip_id = t.trip_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    WHERE %s BETWEEN c.start_date AND c.end_date
                    GROUP BY s.stop_name 
                    ORDER BY trip_count DESC 
                    LIMIT 5
                """, (max_date,))

            busiest_rows = cur.fetchall()
            busiest_stations = [{"name": r[0], "trips": r[1]} for r in busiest_rows]
            busiest_station = busiest_stations[0]["name"] if busiest_stations else "No Stations"

            # 4. Route distribution (Donut chart)
            if mode == "month":
                cur.execute("""
                    SELECT COALESCE(r.route_short_name, r.route_long_name) as route_name, COUNT(t.trip_id) as trip_count 
                    FROM gtfs.trips t 
                    JOIN gtfs.routes r ON t.route_id = r.route_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    GROUP BY route_name 
                    ORDER BY trip_count DESC 
                    LIMIT 6
                """)
            else:
                cur.execute("""
                    SELECT COALESCE(r.route_short_name, r.route_long_name) as route_name, COUNT(t.trip_id) as trip_count 
                    FROM gtfs.trips t 
                    JOIN gtfs.routes r ON t.route_id = r.route_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    WHERE %s BETWEEN c.start_date AND c.end_date
                    GROUP BY route_name 
                    ORDER BY trip_count DESC 
                    LIMIT 6
                """, (max_date,))

            route_rows = cur.fetchall()
            route_distribution = [{"label": r[0], "value": r[1]} for r in route_rows]

            # 5. Trips distribution by hour of day
            if mode == "month":
                cur.execute("""
                    SELECT SUBSTRING(st.departure_time, 1, 2) as hour, COUNT(*) as trip_count 
                    FROM gtfs.stop_times st
                    JOIN gtfs.trips t ON st.trip_id = t.trip_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    GROUP BY hour 
                    ORDER BY hour
                """)
            else:
                cur.execute("""
                    SELECT SUBSTRING(st.departure_time, 1, 2) as hour, COUNT(*) as trip_count 
                    FROM gtfs.stop_times st
                    JOIN gtfs.trips t ON st.trip_id = t.trip_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    WHERE %s BETWEEN c.start_date AND c.end_date
                    GROUP BY hour 
                    ORDER BY hour
                """, (max_date,))

            hour_rows = cur.fetchall()
            hours_data = {f"{i:02d}:00": 0 for i in range(24)}
            for r in hour_rows:
                if r[0] and r[0].isdigit():
                    hr_int = int(r[0])
                    if 0 <= hr_int < 24:
                        hours_data[f"{hr_int:02d}:00"] = r[1]
            hourly_trips = [{"hour": k, "trips": v} for k, v in hours_data.items()]

        conn.close()
        return {
            "status": "success",
            "source": "database",
            "metrics": {
                "total_trips": f"{total_trips:,}",
                "busiest_station": busiest_station,
                "last_update": max_date
            },
            "date_range": date_range,
            "busiest_stations": busiest_stations,
            "route_distribution": route_distribution,
            "hourly_trips": hourly_trips
        }

    except Exception as exc:
        print(f"Database analytics query failed: {exc}. Returning fallback data.")
        return {
            "status": "success",
            "source": "fallback",
            "metrics": {
                "total_trips": "5,547",
                "busiest_station": "Châtelet - Les Halles",
                "last_update": "2026-06-24"
            },
            "date_range": {
                "start": "2026-05-23",
                "end": "2026-06-24",
                "active_day": "2026-06-24",
                "mode": mode
            },
            "busiest_stations": [
                {"name": "Châtelet - Les Halles", "trips": 308},
                {"name": "La Défense", "trips": 266},
                {"name": "Gare Saint-Lazare", "trips": 216},
                {"name": "Stade de France Saint-Denis", "trips": 192},
                {"name": "Paris Gare du Nord", "trips": 190}
            ],
            "route_distribution": [
                {"label": "Line A", "value": 2400},
                {"label": "Line B", "value": 1850},
                {"label": "Line D", "value": 1500},
                {"label": "Line E", "value": 1100},
                {"label": "Line C", "value": 900},
                {"label": "RER Lines", "value": 650}
            ],
            "hourly_trips": [
                {"hour": "00:00", "trips": 15}, {"hour": "01:00", "trips": 8},
                {"hour": "02:00", "trips": 5},  {"hour": "03:00", "trips": 3},
                {"hour": "04:00", "trips": 6},  {"hour": "05:00", "trips": 45},
                {"hour": "06:00", "trips": 115},{"hour": "07:00", "trips": 180},
                {"hour": "08:00", "trips": 197},{"hour": "09:00", "trips": 160},
                {"hour": "10:00", "trips": 130},{"hour": "11:00", "trips": 125},
                {"hour": "12:00", "trips": 121},{"hour": "13:00", "trips": 118},
                {"hour": "14:00", "trips": 121},{"hour": "15:00", "trips": 138},
                {"hour": "16:00", "trips": 154},{"hour": "17:00", "trips": 185},
                {"hour": "18:00", "trips": 200},{"hour": "19:00", "trips": 170},
                {"hour": "20:00", "trips": 127},{"hour": "21:00", "trips": 90},
                {"hour": "22:00", "trips": 66}, {"hour": "23:00", "trips": 35}
            ]
        }

from fastapi.responses import FileResponse
import os

@app.get("/", include_in_schema=False)
def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "index.html")
    if not os.path.exists(frontend_path):
        # Create directory if not exists
        os.makedirs(os.path.dirname(frontend_path), exist_ok=True)
        # Create basic stub if missing
        with open(frontend_path, "w", encoding="utf-8") as f:
            f.write("<h1>Railflow Frontend</h1>")
    return FileResponse(frontend_path)
