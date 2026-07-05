from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class GeometryModel(BaseModel):
    type: str
    coordinates: List[float]

class AgencyModel(BaseModel):
    id: int
    onestop_id: str
    agency_id: Optional[str] = None
    agency_name: str
    agency_url: Optional[str] = None
    agency_timezone: Optional[str] = None
    agency_lang: Optional[str] = None
    agency_phone: Optional[str] = None

class StopModel(BaseModel):
    id: int
    onestop_id: str
    stop_id: Optional[str] = None
    stop_name: Optional[str] = None
    stop_code: Optional[str] = None
    location_type: Optional[int] = 0
    wheelchair_boarding: Optional[int] = 0
    geometry: Optional[GeometryModel] = None
    place: Optional[Dict[str, Any]] = None

class RouteAgencyModel(BaseModel):
    agency_id: Optional[str] = None
    agency_name: Optional[str] = None

class RouteModel(BaseModel):
    id: int
    onestop_id: str
    route_id: Optional[str] = None
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    route_type: Optional[int] = None
    agency: Optional[RouteAgencyModel] = None
