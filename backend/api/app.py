import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from backend.api.fetch_service import fetch_stops, fetch_routes
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="Railflow Fetch API",
    description="Fetches transit data from Transitland API and returns it directly (No DB).",
    version="1.0.0",
)

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
