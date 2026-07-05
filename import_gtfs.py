import os
import zipfile
import csv
import io
import time
import sys
from typing import List, Dict, Any, Type
from pydantic import ValidationError, BaseModel
import psycopg2
from psycopg2.extras import execute_values

# Adjust python path if necessary to find backend module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from backend.models.gtfs import (
    AgencyModel,
    CalendarModel,
    CalendarDateModel,
    RouteModel,
    StopModel,
    TripModel,
    StopTimeModel,
    TransferModel,
    PathwayModel,
    AttributionModel,
    ObjectCodesExtensionModel,
)

# SQL statements to set up schema and tables
CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS gtfs;"

TABLE_CREATION_QUERIES = [
    """
    CREATE TABLE IF NOT EXISTS gtfs.agency (
        agency_id VARCHAR(100) PRIMARY KEY,
        agency_name VARCHAR(255) NOT NULL,
        agency_url VARCHAR(255) NOT NULL,
        agency_timezone VARCHAR(100) NOT NULL,
        agency_lang VARCHAR(10),
        agency_phone VARCHAR(50),
        agency_email VARCHAR(255),
        agency_fare_url VARCHAR(255)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.calendar (
        service_id VARCHAR(100) PRIMARY KEY,
        monday INT NOT NULL,
        tuesday INT NOT NULL,
        wednesday INT NOT NULL,
        thursday INT NOT NULL,
        friday INT NOT NULL,
        saturday INT NOT NULL,
        sunday INT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.calendar_dates (
        service_id VARCHAR(100) NOT NULL,
        date DATE NOT NULL,
        exception_type INT NOT NULL,
        PRIMARY KEY (service_id, date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.stops (
        stop_id VARCHAR(100) PRIMARY KEY,
        stop_code VARCHAR(50),
        stop_name VARCHAR(255),
        stop_desc TEXT,
        stop_lon DOUBLE PRECISION,
        stop_lat DOUBLE PRECISION,
        zone_id VARCHAR(100),
        stop_url VARCHAR(255),
        location_type INT DEFAULT 0,
        parent_station VARCHAR(100),
        stop_timezone VARCHAR(100),
        level_id VARCHAR(100),
        wheelchair_boarding INT DEFAULT 0,
        platform_code VARCHAR(50),
        stop_access VARCHAR(100)
    );
    CREATE INDEX IF NOT EXISTS idx_stops_latlon ON gtfs.stops (stop_lat, stop_lon);
    CREATE INDEX IF NOT EXISTS idx_stops_parent_station ON gtfs.stops (parent_station);
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.routes (
        route_id VARCHAR(100) PRIMARY KEY,
        agency_id VARCHAR(100) REFERENCES gtfs.agency(agency_id) ON DELETE SET NULL,
        route_short_name VARCHAR(50),
        route_long_name VARCHAR(255),
        route_desc TEXT,
        route_type INT NOT NULL,
        route_url VARCHAR(255),
        route_color VARCHAR(10),
        route_text_color VARCHAR(10),
        route_sort_order INT
    );
    CREATE INDEX IF NOT EXISTS idx_routes_agency_id ON gtfs.routes (agency_id);
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.trips (
        route_id VARCHAR(100) REFERENCES gtfs.routes(route_id) ON DELETE CASCADE,
        service_id VARCHAR(100),
        trip_id VARCHAR(100) PRIMARY KEY,
        trip_headsign VARCHAR(255),
        trip_short_name VARCHAR(255),
        direction_id INT,
        block_id VARCHAR(100),
        shape_id VARCHAR(100),
        wheelchair_accessible INT DEFAULT 0,
        bikes_allowed INT DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_trips_route_id ON gtfs.trips (route_id);
    CREATE INDEX IF NOT EXISTS idx_trips_service_id ON gtfs.trips (service_id);
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.stop_times (
        trip_id VARCHAR(100) REFERENCES gtfs.trips(trip_id) ON DELETE CASCADE,
        arrival_time VARCHAR(20),
        departure_time VARCHAR(20),
        start_pickup_drop_off_window VARCHAR(20),
        end_pickup_drop_off_window VARCHAR(20),
        stop_id VARCHAR(100) REFERENCES gtfs.stops(stop_id) ON DELETE CASCADE,
        stop_sequence INT NOT NULL,
        pickup_type INT DEFAULT 0,
        drop_off_type INT DEFAULT 0,
        local_zone_id VARCHAR(100),
        stop_headsign VARCHAR(255),
        timepoint INT DEFAULT 1,
        pickup_booking_rule_id VARCHAR(100),
        drop_off_booking_rule_id VARCHAR(100),
        PRIMARY KEY (trip_id, stop_sequence)
    );
    CREATE INDEX IF NOT EXISTS idx_stop_times_stop_id ON gtfs.stop_times (stop_id);
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.transfers (
        id SERIAL PRIMARY KEY,
        from_stop_id VARCHAR(100) REFERENCES gtfs.stops(stop_id) ON DELETE CASCADE,
        to_stop_id VARCHAR(100) REFERENCES gtfs.stops(stop_id) ON DELETE CASCADE,
        transfer_type INT NOT NULL,
        min_transfer_time INT
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_transfers_from_to ON gtfs.transfers (from_stop_id, to_stop_id);
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.pathways (
        pathway_id VARCHAR(100) PRIMARY KEY,
        from_stop_id VARCHAR(100) REFERENCES gtfs.stops(stop_id) ON DELETE CASCADE,
        to_stop_id VARCHAR(100) REFERENCES gtfs.stops(stop_id) ON DELETE CASCADE,
        pathway_mode INT NOT NULL,
        is_bidirectional INT NOT NULL,
        length DOUBLE PRECISION,
        traversal_time INT,
        stair_count INT,
        max_slope DOUBLE PRECISION,
        min_width DOUBLE PRECISION,
        signposted_as VARCHAR(255),
        reversed_signposted_as VARCHAR(255)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.attributions (
        id SERIAL PRIMARY KEY,
        attribution_id VARCHAR(100),
        route_id VARCHAR(100) REFERENCES gtfs.routes(route_id) ON DELETE CASCADE,
        trip_id VARCHAR(100) REFERENCES gtfs.trips(trip_id) ON DELETE CASCADE,
        is_operator INT,
        organization_name VARCHAR(255) NOT NULL,
        attribution_url VARCHAR(255),
        attribution_email VARCHAR(255),
        attribution_phone VARCHAR(50)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS gtfs.object_codes_extension (
        object_type VARCHAR(100) NOT NULL,
        object_id VARCHAR(100) NOT NULL,
        object_system VARCHAR(100),
        object_code VARCHAR(100),
        PRIMARY KEY (object_type, object_id, object_code)
    );
    """
]

# Mapping of file names (without .txt) to their corresponding details
GTFS_FILES_CONFIG: Dict[str, Dict[str, Any]] = {
    "agency": {
        "model": AgencyModel,
        "table": "gtfs.agency",
        "columns": [
            "agency_id", "agency_name", "agency_url", "agency_timezone",
            "agency_lang", "agency_phone", "agency_email", "agency_fare_url"
        ]
    },
    "calendar": {
        "model": CalendarModel,
        "table": "gtfs.calendar",
        "columns": [
            "service_id", "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday", "start_date", "end_date"
        ]
    },
    "calendar_dates": {
        "model": CalendarDateModel,
        "table": "gtfs.calendar_dates",
        "columns": ["service_id", "date", "exception_type"]
    },
    "stops": {
        "model": StopModel,
        "table": "gtfs.stops",
        "columns": [
            "stop_id", "stop_code", "stop_name", "stop_desc", "stop_lon",
            "stop_lat", "zone_id", "stop_url", "location_type", "parent_station",
            "stop_timezone", "level_id", "wheelchair_boarding", "platform_code",
            "stop_access"
        ]
    },
    "routes": {
        "model": RouteModel,
        "table": "gtfs.routes",
        "columns": [
            "route_id", "agency_id", "route_short_name", "route_long_name",
            "route_desc", "route_type", "route_url", "route_color",
            "route_text_color", "route_sort_order"
        ]
    },
    "trips": {
        "model": TripModel,
        "table": "gtfs.trips",
        "columns": [
            "route_id", "service_id", "trip_id", "trip_headsign",
            "trip_short_name", "direction_id", "block_id", "shape_id",
            "wheelchair_accessible", "bikes_allowed"
        ]
    },
    "stop_times": {
        "model": StopTimeModel,
        "table": "gtfs.stop_times",
        "columns": [
            "trip_id", "arrival_time", "departure_time", "start_pickup_drop_off_window",
            "end_pickup_drop_off_window", "stop_id", "stop_sequence", "pickup_type",
            "drop_off_type", "local_zone_id", "stop_headsign", "timepoint",
            "pickup_booking_rule_id", "drop_off_booking_rule_id"
        ]
    },
    "transfers": {
        "model": TransferModel,
        "table": "gtfs.transfers",
        "columns": [
            "from_stop_id", "to_stop_id", "transfer_type", "min_transfer_time"
        ]
    },
    "pathways": {
        "model": PathwayModel,
        "table": "gtfs.pathways",
        "columns": [
            "pathway_id", "from_stop_id", "to_stop_id", "pathway_mode",
            "is_bidirectional", "length", "traversal_time", "stair_count",
            "max_slope", "min_width", "signposted_as", "reversed_signposted_as"
        ]
    },
    "attributions": {
        "model": AttributionModel,
        "table": "gtfs.attributions",
        "columns": [
            "attribution_id", "route_id", "trip_id", "is_operator",
            "organization_name", "attribution_url", "attribution_email", "attribution_phone"
        ]
    },
    "object_codes_extension": {
        "model": ObjectCodesExtensionModel,
        "table": "gtfs.object_codes_extension",
        "columns": ["object_type", "object_id", "object_system", "object_code"]
    }
}

# The files MUST be imported in this order to satisfy database referential integrity
IMPORT_ORDER = [
    "agency",
    "calendar",
    "calendar_dates",
    "stops",
    "routes",
    "trips",
    "stop_times",
    "transfers",
    "pathways",
    "attributions",
    "object_codes_extension"
]

def setup_database(conn):
    """Creates the schema and tables in the database."""
    print("Setting up database schema and tables...")
    with conn.cursor() as cur:
        cur.execute(CREATE_SCHEMA_SQL)
        for query in TABLE_CREATION_QUERIES:
            cur.execute(query)
    conn.commit()
    print("Database schema and tables set up successfully.")

def clear_database_gtfs(conn):
    """Drops the gtfs schema completely (for reset option)."""
    print("Dropping existing gtfs schema (reset)...")
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS gtfs CASCADE;")
    conn.commit()
    print("GTFS schema cleared.")

def import_gtfs_file(zip_ref: zipfile.ZipFile, name: str, config: Dict[str, Any], conn) -> None:
    """Parses a GTFS text file from zip, validates with Pydantic, and performs batch insert."""
    file_path_in_zip = f"data/{name}.txt"
    
    # Check if file exists in the zip
    if file_path_in_zip not in zip_ref.namelist():
        print(f"Skipping {name}.txt (file not found in zip)")
        return

    print(f"Processing {name}.txt...")
    start_time = time.time()
    
    model_class: Type[BaseModel] = config["model"]
    table_name: str = config["table"]
    columns: List[str] = config["columns"]
    
    # Read CSV file contents
    with zip_ref.open(file_path_in_zip) as f:
        # Decode as utf-8 (ignoring byte order mark and replacing invalid characters)
        text_stream = io.TextIOWrapper(f, encoding='utf-8-sig', errors='replace')
        reader = csv.DictReader(text_stream)
        
        valid_rows = []
        validation_failed_count = 0
        total_rows_read = 0
        
        # Read and validate rows
        for row in reader:
            total_rows_read += 1
            try:
                # Instantiate Pydantic model for validation
                validated_model = model_class(**row)
                
                # Convert the validated model to a tuple matching the column list
                row_tuple = tuple(getattr(validated_model, col) for col in columns)
                valid_rows.append(row_tuple)
            except ValidationError as e:
                validation_failed_count += 1
                if validation_failed_count <= 5:
                    print(f"Validation error in row {total_rows_read}: {e}")
                elif validation_failed_count == 6:
                    print("More validation errors hidden...")

        # Batch insert valid rows
        if valid_rows:
            col_list_str = ", ".join(columns)
            insert_query = f"INSERT INTO {table_name} ({col_list_str}) VALUES %s ON CONFLICT DO NOTHING"
            
            with conn.cursor() as cur:
                execute_values(cur, insert_query, valid_rows)
            conn.commit()
            
            elapsed = time.time() - start_time
            print(f"Successfully imported {len(valid_rows)}/{total_rows_read} rows into {table_name} in {elapsed:.2f}s "
                  f"(Failed validation: {validation_failed_count})")
        else:
            print(f"No valid rows to import for {name}.txt (Total read: {total_rows_read})")

def main():
    zip_path = "data/data.zip"
    
    if not os.path.exists(zip_path):
        print(f"Error: ZIP file not found at {zip_path}")
        return

    # Optional reset flag
    reset = "--reset" in sys.argv

    conn = get_db_connection()
    try:
        if reset:
            clear_database_gtfs(conn)
            
        setup_database(conn)
        
        print(f"Opening archive: {zip_path}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Process each file in the required order
            for name in IMPORT_ORDER:
                config = GTFS_FILES_CONFIG[name]
                import_gtfs_file(zip_ref, name, config, conn)
                
        print("\nIngestion completed perfectly! All GTFS data is now in PostgreSQL.")
        
    except Exception as e:
        print(f"An error occurred during import: {e}", file=sys.stderr)
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
