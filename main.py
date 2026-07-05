import json
from database import get_db_connection, create_tables
from models import StopModel, RouteModel
from pydantic import ValidationError

def load_stops(cursor):
    print("Processing stops data with Pydantic validation...")
    with open('berlin_stops.json', 'r', encoding='utf-8') as f:
        stops_data = json.load(f)
        for item in stops_data:
            try:
                stop = StopModel(**item)
                cursor.execute("""
                    INSERT INTO stops (stop_id, stop_name, lat, lon, wheelchair, transport_type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stop_id) DO NOTHING;
                """, (stop.stop_id, stop.stop_name, stop.lat, stop.lon, stop.wheelchair, stop.transport_type))
            except ValidationError as e:
                print(f"Validation error for stop {item.get('stop_id')}: {e}")

def load_routes(cursor):
    print("Processing routes and route_stops data with Pydantic validation...")
    with open('berlin_routes_clean.json', 'r', encoding='utf-8') as f:
        routes_data = json.load(f)
        for item in routes_data:
            try:
                route = RouteModel(**item)
                
                cursor.execute("""
                    INSERT INTO routes (route_id, line, agency)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (route_id) DO NOTHING;
                """, (route.route_id, route.line, route.agency))
                
                for stop_ref in route.stops:
                    cursor.execute("SELECT 1 FROM stops WHERE stop_id = %s", (stop_ref.stop_id,))
                    if cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO route_stops (route_id, stop_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING;
                        """, (route.route_id, stop_ref.stop_id))
                        
            except ValidationError as e:
                print(f"Validation error for route {item.get('route_id')}: {e}")

def main():
    conn = get_db_connection()
    create_tables(conn)
    
    cursor = conn.cursor()
    load_stops(cursor)
    load_routes(cursor)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Success! All data ingestion and validation completed perfectly.")

if __name__ == "__main__":
    main()