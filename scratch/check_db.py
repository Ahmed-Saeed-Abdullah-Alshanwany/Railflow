import sys
import os
import time

sys.path.append(r"c:\Users\Eng.Mohamed\OneDrive - Faculty Of Engineering (Tanta University)\Desktop\Railflow")

from backend.services.routing_service import find_routes

start = time.time()
print("Starting Python-optimized bi-directional routing from Nation to Cité Universitaire...")
try:
    result = find_routes(
        start_stop_id="Nation",
        end_stop_id="Cité Universitaire",
        start_time_str="09:00:00",
        limit=3
    )
    duration = time.time() - start
    print(f"Routing completed in {duration:.4f} seconds.")
    print("Options found:", len(result.get("options", [])))
    if result.get("options"):
        print("First Option Details:")
        print(result["options"][0])
except Exception as e:
    print("Routing failed:", e)
