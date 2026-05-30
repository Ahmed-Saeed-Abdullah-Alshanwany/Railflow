from pydantic import BaseModel
from typing import List, Optional

class StopModel(BaseModel):
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    wheelchair: int = 0
    transport_type: Optional[str] = None

class RouteStopModel(BaseModel):
    stop_id: str

class RouteModel(BaseModel):
    route_id: str
    line: str
    agency: Optional[str] = ""
    stops: List[RouteStopModel] = []