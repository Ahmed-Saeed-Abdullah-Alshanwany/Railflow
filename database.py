import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Return a live psycopg2 connection using environment variables."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5435"),
    )


def create_tables(conn):
    """Create all project tables if they do not already exist."""
    cursor = conn.cursor()
    print("Creating tables if they do not exist...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stops (
            stop_id        VARCHAR(100) PRIMARY KEY,
            onestop_id     VARCHAR(150) UNIQUE,
            stop_name      VARCHAR(255),
            lat            DOUBLE PRECISION,
            lon            DOUBLE PRECISION,
            wheelchair     INT DEFAULT 0,
            transport_type VARCHAR(50),
            country        VARCHAR(100),
            state          VARCHAR(100),
            platform_code  VARCHAR(20),
            location_type  INT DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_stops_latlon ON stops (lat, lon);

        CREATE TABLE IF NOT EXISTS routes (
            route_id VARCHAR(100) PRIMARY KEY,
            line     VARCHAR(50),
            agency   VARCHAR(150)
        );

        CREATE TABLE IF NOT EXISTS route_stops (
            route_id VARCHAR(100) REFERENCES routes(route_id) ON DELETE CASCADE,
            stop_id  VARCHAR(100) REFERENCES stops(stop_id)   ON DELETE CASCADE,
            PRIMARY KEY (route_id, stop_id)
        );

        CREATE TABLE IF NOT EXISTS sync_cursors (
            entity_type VARCHAR(50) PRIMARY KEY,
            operator_id VARCHAR(150),
            last_after  BIGINT,
            last_count  INT DEFAULT 0,
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    conn.commit()
    cursor.close()
    print("Tables ready.")


def get_cursor(conn, entity_type: str):
    """Return (last_after, last_count) for an entity type."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT last_after, last_count FROM sync_cursors WHERE entity_type = %s",
            (entity_type,),
        )
        row = cur.fetchone()
        if row is None:
            return None, 0
        return row[0], row[1]


def save_cursor(conn, entity_type: str, operator_id: str, last_after, total_count: int):
    """Upsert the sync cursor for an entity type."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sync_cursors (entity_type, operator_id, last_after, last_count, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (entity_type) DO UPDATE
                SET operator_id = EXCLUDED.operator_id,
                    last_after  = EXCLUDED.last_after,
                    last_count  = EXCLUDED.last_count,
                    updated_at  = NOW()
        """, (entity_type, operator_id, last_after, total_count))
    conn.commit()