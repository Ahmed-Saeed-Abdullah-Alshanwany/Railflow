import sys, os
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from backend.services.departures_service import get_connection

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print("=== Test Connection: Gare du Nord -> La Défense ===")
c = get_connection("Gare du Nord", "La Défense", "09:00:00", 3)
print("From:", c.get("from_station"), "-> To:", c.get("to_station"))
print("Direct count:", c.get("direct_count"), "Transfer count:", c.get("transfer_count"))
for opt in c.get("connections", []):
    print(f" - {opt['type']} | Departs: {opt['departs_at']} | Arrives: {opt['arrives_at']}")
    if opt["type"] == "1-transfer":
        print(f"   Transfer at {opt['transfer_stop_name']} (arr {opt['arrives_transfer']} -> dep {opt['departs_transfer']})")
