import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv; load_dotenv()
from backend.services.departures_service import get_departures, get_connection
from backend.services.agent_service import TransitAgentService
import json

print("=== Import OK ===")

# Test get_departures
print("\n--- get_departures('Nation', '09:00:00', 5) ---")
r = get_departures("Nation", "09:00:00", 5)
print("Station    :", r.get("station_name"))
print("Active date:", r.get("active_date"))
print("Routes today:", r.get("total_routes"))
print("Departures :", len(r.get("departures", [])))
for d in r.get("departures", [])[:3]:
    print(f"  {d['departs_at']} | {d['route']} -> {d['direction']}")

# Test get_connection
print("\n--- get_connection('Nation', 'Chatou', '09:00:00', 3) ---")
c = get_connection("Nation", "Chatou", "09:00:00", 3)
print("From:", c.get("from_station"), "-> To:", c.get("to_station"))
print("Direct:", c.get("direct_count"), " Transfer:", c.get("transfer_count"))
for opt in c.get("connections", [])[:3]:
    t = opt.get("type")
    if t == "direct":
        print(f"  [DIRECT] {opt['departs_at']} -> {opt['arrives_at']} via {opt['route']}")
    else:
        print(f"  [TRANSFER] {opt['departs_at']} -> {opt['arrives_at']} via {opt.get('leg1_route')} + {opt.get('leg2_route')}")

print("\n=== All done ===")
