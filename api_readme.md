# Railflow Transit API Documentation

This document contains the documentation for the primary APIs we rely on to extract transit data (Stations, Routes, and Agencies).

## How to Get an API Key
To obtain a key that allows you to fetch this data for free:
1. Go to the following link: [Transitland Sign Up](https://www.transit.land/documentation/index#sign-up)
2. Create a new account.
3. After logging in, go to your Dashboard.
4. Copy the `API Key` and place it in the `.env` file in your project like this:
   `TRANSITLAND_API_KEY=your_key_here`

---

## 1. Stops Endpoint
**Endpoint:** `GET /api/v2/rest/stops`

This endpoint returns all transit stops (train stations, bus stops, etc.).

**Approved Schema (based on our models):**
```python
class StopModel(BaseModel):
    id: int
    onestop_id: str
    stop_id: Optional[str]
    stop_name: Optional[str]
    stop_code: Optional[str]
    location_type: Optional[int]
    wheelchair_boarding: Optional[int]
    geometry: Optional[GeometryModel]
    place: Optional[Dict[str, Any]]
```

---

## 2. Routes Endpoint
**Endpoint:** `GET /api/v2/rest/routes`

This endpoint returns the names and details of transit routes.

**Approved Schema:**
```python
class RouteModel(BaseModel):
    id: int
    onestop_id: str
    route_id: Optional[str]
    route_short_name: Optional[str]
    route_long_name: Optional[str]
    route_type: Optional[int]
    agency: Optional[RouteAgencyModel]
```

---

## 3. Agencies Endpoint
**Endpoint:** `GET /api/v2/rest/agencies`

This endpoint returns data about the company that operates the transit lines (e.g., S-Bahn Berlin).

**Approved Schema:**
```python
class AgencyModel(BaseModel):
    id: int
    onestop_id: str
    agency_id: Optional[str]
    agency_name: str
    agency_url: Optional[str]
    agency_timezone: Optional[str]
    agency_lang: Optional[str]
    agency_phone: Optional[str]
```
