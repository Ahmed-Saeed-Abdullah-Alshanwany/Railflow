import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from backend.api.fetch_service import fetch_stops, fetch_routes
from pydantic import BaseModel
from backend.api.routers.agent import router as agent_router
from backend.api.routers.stats import router as stats_router

load_dotenv()

app = FastAPI(
    title="Railflow Fetch API",
    description="Fetches transit data from Transitland API and returns it directly (No DB).",
    version="1.0.0",
)

app.include_router(agent_router)
app.include_router(stats_router)

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
