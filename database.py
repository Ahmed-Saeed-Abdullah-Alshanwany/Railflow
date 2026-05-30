import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

def create_tables(conn):
    cursor = conn.cursor()
    print("Creating tables if they do not exist...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stops (
            stop_id VARCHAR(100) PRIMARY KEY,
            stop_name VARCHAR(255),
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            wheelchair INT,
            transport_type VARCHAR(50)
        );

        CREATE TABLE IF NOT EXISTS routes (
            route_id VARCHAR(100) PRIMARY KEY,
            line VARCHAR(50),
            agency VARCHAR(150)
        );

        CREATE TABLE IF NOT EXISTS route_stops (
            route_id VARCHAR(100) REFERENCES routes(route_id),
            stop_id VARCHAR(100) REFERENCES stops(stop_id),
            PRIMARY KEY (route_id, stop_id)
        );
    """)
    conn.commit()
    cursor.close()