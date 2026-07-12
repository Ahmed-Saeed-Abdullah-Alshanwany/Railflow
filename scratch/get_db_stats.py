import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import get_db_connection

def main():
    load_dotenv()
    print("Connecting to database...")
    try:
        conn = get_db_connection()
        print("Connected successfully!")
    except Exception as e:
        print("Failed to connect to database:", e)
        return

    try:
        with conn.cursor() as cur:
            # Check existing tables in gtfs schema
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'gtfs'
            """)
            tables = [row[0] for row in cur.fetchall()]
            print("Tables in schema 'gtfs':", tables)
            
            # Print row counts for main tables
            for table in ['trips', 'stop_times', 'stops', 'routes', 'calendar']:
                if table in tables:
                    cur.execute(f"SELECT COUNT(*) FROM gtfs.{table}")
                    count = cur.fetchone()[0]
                    print(f"Row count in gtfs.{table}: {count:,}")
                else:
                    print(f"Table gtfs.{table} does not exist.")

            # Let's check unique service days or trip dates if calendar is used
            if 'calendar' in tables:
                cur.execute("SELECT MIN(start_date), MAX(end_date) FROM gtfs.calendar")
                row = cur.fetchone()
                print(f"Calendar range: {row[0]} to {row[1]}")

            # Top 3 busiest stations count query
            if 'stop_times' in tables and 'stops' in tables:
                cur.execute("""
                    SELECT s.stop_name, COUNT(*) 
                    FROM gtfs.stop_times st
                    JOIN gtfs.stops s ON st.stop_id = s.stop_id
                    GROUP BY s.stop_name
                    ORDER BY COUNT(*) DESC
                    LIMIT 3
                """)
                print("Top 3 busiest stations by stop_times occurrences:")
                for row in cur.fetchall():
                    print(f"  - {row[0]}: {row[1]:,} stops")

    except Exception as e:
        print("Query error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
