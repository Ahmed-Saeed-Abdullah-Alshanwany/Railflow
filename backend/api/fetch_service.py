"""
fetch_service.py
--------------------
Service to fetch stops and routes from Transitland without storing them in DB.
"""

from backend.transitland.extractors.stops_extractor import StopsExtractor
from backend.transitland.extractors.berlin_extractor import BerlinExtractor

def fetch_stops(operator_id: str, limit: int = 100, after: int = None) -> dict:
    extractor = StopsExtractor()
    stops, next_cursor = extractor.extract(
        operator_onestop_id=operator_id,
        limit=limit,
        after=after,
    )
    
    return {
        "fetched": len(stops),
        "next_after": next_cursor,
        "data": stops
    }

def fetch_routes(operator_id: str, limit: int = 50, after: int = None) -> dict:
    extractor = BerlinExtractor()
    extractor.OPERATOR_ID = operator_id
    routes, next_cursor = extractor.extract_routes(
        limit=limit,
        after=after,
    )
    
    return {
        "fetched": len(routes),
        "next_after": next_cursor,
        "data": routes
    }
