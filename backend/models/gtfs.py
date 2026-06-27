from pydantic import BaseModel, model_validator, Field, field_validator
from typing import Optional
import datetime

class GTFSBaseModel(BaseModel):
    """Base model that automatically converts empty or whitespace strings to None."""
    @model_validator(mode='before')
    @classmethod
    def empty_str_to_none(cls, data: any) -> any:
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if isinstance(v, str):
                    stripped = v.strip()
                    cleaned[k] = None if stripped == "" else stripped
                else:
                    cleaned[k] = v
            return cleaned
        return data

class AgencyModel(GTFSBaseModel):
    agency_id: Optional[str] = None
    agency_name: str
    agency_url: str
    agency_timezone: str
    agency_lang: Optional[str] = None
    agency_phone: Optional[str] = None
    agency_email: Optional[str] = None
    agency_fare_url: Optional[str] = None

class CalendarModel(GTFSBaseModel):
    service_id: str
    monday: int = Field(ge=0, le=1)
    tuesday: int = Field(ge=0, le=1)
    wednesday: int = Field(ge=0, le=1)
    thursday: int = Field(ge=0, le=1)
    friday: int = Field(ge=0, le=1)
    saturday: int = Field(ge=0, le=1)
    sunday: int = Field(ge=0, le=1)
    start_date: str
    end_date: str

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.datetime.strptime(v, "%Y%m%d")
            return v
        except ValueError:
            raise ValueError(f"Date must be in YYYYMMDD format, got: {v}")

class CalendarDateModel(GTFSBaseModel):
    service_id: str
    date: str
    exception_type: int = Field(ge=1, le=2)

    @field_validator('date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.datetime.strptime(v, "%Y%m%d")
            return v
        except ValueError:
            raise ValueError(f"Date must be in YYYYMMDD format, got: {v}")

class RouteModel(GTFSBaseModel):
    route_id: str
    agency_id: Optional[str] = None
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    route_desc: Optional[str] = None
    route_type: int
    route_url: Optional[str] = None
    route_color: Optional[str] = None
    route_text_color: Optional[str] = None
    route_sort_order: Optional[int] = None

    @model_validator(mode='after')
    def check_short_or_long_name(self) -> 'RouteModel':
        if not self.route_short_name and not self.route_long_name:
            raise ValueError("Either route_short_name or route_long_name must be provided")
        return self

class StopModel(GTFSBaseModel):
    stop_id: str
    stop_code: Optional[str] = None
    stop_name: Optional[str] = None
    stop_desc: Optional[str] = None
    stop_lon: Optional[float] = Field(None, ge=-180.0, le=180.0)
    stop_lat: Optional[float] = Field(None, ge=-90.0, le=90.0)
    zone_id: Optional[str] = None
    stop_url: Optional[str] = None
    location_type: Optional[int] = Field(0, ge=0, le=4)
    parent_station: Optional[str] = None
    stop_timezone: Optional[str] = None
    level_id: Optional[str] = None
    wheelchair_boarding: Optional[int] = Field(0, ge=0, le=2)
    platform_code: Optional[str] = None
    stop_access: Optional[str] = None

class TripModel(GTFSBaseModel):
    route_id: str
    service_id: str
    trip_id: str
    trip_headsign: Optional[str] = None
    trip_short_name: Optional[str] = None
    direction_id: Optional[int] = Field(None, ge=0, le=1)
    block_id: Optional[str] = None
    shape_id: Optional[str] = None
    wheelchair_accessible: Optional[int] = Field(0, ge=0, le=2)
    bikes_allowed: Optional[int] = Field(0, ge=0, le=2)

class StopTimeModel(GTFSBaseModel):
    trip_id: str
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    start_pickup_drop_off_window: Optional[str] = None
    end_pickup_drop_off_window: Optional[str] = None
    stop_id: str
    stop_sequence: int = Field(ge=0)
    pickup_type: Optional[int] = Field(0, ge=0, le=3)
    drop_off_type: Optional[int] = Field(0, ge=0, le=3)
    local_zone_id: Optional[str] = None
    stop_headsign: Optional[str] = None
    timepoint: Optional[int] = Field(1, ge=0, le=1)
    pickup_booking_rule_id: Optional[str] = None
    drop_off_booking_rule_id: Optional[str] = None

class TransferModel(GTFSBaseModel):
    from_stop_id: str
    to_stop_id: str
    transfer_type: int = Field(ge=0, le=3)
    min_transfer_time: Optional[int] = Field(None, ge=0)

class PathwayModel(GTFSBaseModel):
    pathway_id: str
    from_stop_id: str
    to_stop_id: str
    pathway_mode: int = Field(ge=1, le=7)
    is_bidirectional: int = Field(ge=0, le=1)
    length: Optional[float] = Field(None, ge=0.0)
    traversal_time: Optional[int] = Field(None, ge=0)
    stair_count: Optional[int] = Field(None)
    max_slope: Optional[float] = Field(None)
    min_width: Optional[float] = Field(None, ge=0.0)
    signposted_as: Optional[str] = None
    reversed_signposted_as: Optional[str] = None

class AttributionModel(GTFSBaseModel):
    attribution_id: Optional[str] = None
    route_id: Optional[str] = None
    trip_id: Optional[str] = None
    is_operator: Optional[int] = Field(None, ge=0, le=1)
    organization_name: str
    attribution_url: Optional[str] = None
    attribution_email: Optional[str] = None
    attribution_phone: Optional[str] = None

class ObjectCodesExtensionModel(GTFSBaseModel):
    object_type: str
    object_id: str
    object_system: Optional[str] = None
    object_code: str
