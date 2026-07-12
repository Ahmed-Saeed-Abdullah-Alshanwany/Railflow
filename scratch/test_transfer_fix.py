import sys, os
sys.path.insert(0, ".")
from database import get_db_connection
from backend.services.departures_service import _resolve_stop, _family_ids, _active_date

conn = get_db_connection()
try:
    with conn.cursor() as cur:
        active_date = _active_date(cur)
        from_stop = _resolve_stop(cur, "Gare du Nord")
        to_stop = _resolve_stop(cur, "La Défense")
        from_ids = _family_ids(cur, from_stop["stop_id"], from_stop["parent_station"])
        to_ids = _family_ids(cur, to_stop["stop_id"], to_stop["parent_station"])
        
        after_time = "09:00:00"
        
        # 1. Fetch legs1: origin -> intermediate (get intermediate stop's parent_station)
        cur.execute("""
            SELECT
                st1.trip_id,
                st1.departure_time,
                st_mid.stop_id,
                COALESCE(s_mid.parent_station, st_mid.stop_id) AS transfer_station,
                st_mid.arrival_time,
                COALESCE(r1.route_short_name, r1.route_long_name)
            FROM gtfs.stop_times st1
            JOIN gtfs.stop_times st_mid ON st1.trip_id = st_mid.trip_id AND st_mid.stop_sequence > st1.stop_sequence
            JOIN gtfs.stops s_mid ON st_mid.stop_id = s_mid.stop_id
            JOIN gtfs.trips t1 ON st1.trip_id = t1.trip_id
            JOIN gtfs.routes r1 ON t1.route_id = r1.route_id
            JOIN gtfs.calendar c1 ON t1.service_id = c1.service_id
            WHERE st1.stop_id = ANY(%s)
              AND %s BETWEEN c1.start_date AND c1.end_date
              AND st1.departure_time >= %s
            ORDER BY st1.departure_time ASC
            LIMIT 400
        """, (from_ids, active_date, after_time))
        legs1 = cur.fetchall()
        print("legs1:", len(legs1))

        if legs1:
            # Get unique parent transfer stations
            transfer_stations = list({r[3] for r in legs1})
            print("Transfer stations:", len(transfer_stations), transfer_stations[:5])
            
            # Find all stop_ids that belong to these transfer stations
            cur.execute("""
                SELECT stop_id, COALESCE(parent_station, stop_id)
                FROM gtfs.stops
                WHERE parent_station = ANY(%s) OR stop_id = ANY(%s)
            """, (transfer_stations, transfer_stations))
            stop_to_parent = {r[0]: r[1] for r in cur.fetchall()}
            transfer_stop_ids = list(stop_to_parent.keys())
            
            # Fetch legs2: intermediate -> destination (filtered to transfer_stop_ids)
            cur.execute("""
                SELECT
                    st_mid.trip_id,
                    COALESCE(s_mid.parent_station, st_mid.stop_id) AS transfer_station,
                    st_mid.departure_time,
                    st2.arrival_time,
                    COALESCE(r2.route_short_name, r2.route_long_name),
                    st_mid.stop_id
                FROM gtfs.stop_times st_mid
                JOIN gtfs.stops s_mid ON st_mid.stop_id = s_mid.stop_id
                JOIN gtfs.stop_times st2 ON st_mid.trip_id = st2.trip_id AND st2.stop_sequence > st_mid.stop_sequence
                JOIN gtfs.trips t2 ON st_mid.trip_id = t2.trip_id
                JOIN gtfs.routes r2 ON t2.route_id = r2.route_id
                JOIN gtfs.calendar c2 ON t2.service_id = c2.service_id
                WHERE st_mid.stop_id = ANY(%s)
                  AND st2.stop_id = ANY(%s)
                  AND %s BETWEEN c2.start_date AND c2.end_date
                  AND st_mid.departure_time >= %s
                ORDER BY st_mid.departure_time ASC
                LIMIT 400
            """, (transfer_stop_ids, to_ids, active_date, after_time))
            legs2 = cur.fetchall()
            print("legs2:", len(legs2))

            # Group legs1 and legs2 by parent transfer_station
            start_by_transfer = {}
            for r in legs1:
                t_station = r[3]
                start_by_transfer.setdefault(t_station, []).append(r)

            end_by_transfer = {}
            for r in legs2:
                t_station = r[1]
                end_by_transfer.setdefault(t_station, []).append(r)

            common = set(start_by_transfer.keys()) & set(end_by_transfer.keys())
            print("Common parent transfers:", common)
            
            options = []
            for t_station in common:
                starts = start_by_transfer[t_station]
                ends = end_by_transfer[t_station]
                for s in starts:
                    for e in ends:
                        arr1 = s[4] # arrival time at transfer
                        dep2 = e[2] # departure time from transfer
                        if dep2 >= arr1:
                            # Verify transfer time buffer (e.g. 2 to 120 minutes)
                            h1, m1, s1 = map(int, arr1.split(':'))
                            h2, m2, s2 = map(int, dep2.split(':'))
                            diff = (h2 * 60 + m2) - (h1 * 60 + m1)
                            if 2 <= diff <= 120:
                                options.append({
                                    "leg1_route": s[5],
                                    "departs_at": s[1],
                                    "transfer_station": t_station,
                                    "arrives_transfer": arr1,
                                    "leg2_route": e[4],
                                    "departs_transfer": dep2,
                                    "arrives_at": e[3],
                                })
            
            options.sort(key=lambda x: (x["arrives_at"], x["departs_at"]))
            print(f"Found {len(options)} options.")
            for opt in options[:3]:
                # Get parent station name
                cur.execute("SELECT stop_name FROM gtfs.stops WHERE stop_id = %s LIMIT 1", (opt["transfer_station"],))
                row = cur.fetchone()
                opt["transfer_station_name"] = row[0] if row else opt["transfer_station"]
                print(opt)
finally:
    conn.close()
