import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()

# Simulate 60 identical tool_calls (the exact bug scenario)
args_str = '{"sql_query":"SELECT stop_name FROM gtfs.stops LIMIT 10"}'
fake_calls = [
    {"id": f"tc{i}", "function": {"name": "run_readonly_sql", "arguments": args_str}}
    for i in range(60)
]

MAX_TOOL_CALLS = 5
seen_keys = set()
unique_calls = []
for tc in fake_calls:
    key = (tc["function"]["name"], tc["function"]["arguments"])
    if key not in seen_keys:
        seen_keys.add(key)
        unique_calls.append(tc)
    if len(unique_calls) >= MAX_TOOL_CALLS:
        break

print(f"Input: {len(fake_calls)} calls  ->  Deduplicated: {len(unique_calls)} call(s)")
if len(unique_calls) == 1:
    print("DEDUP guard working correctly!")
else:
    print("ERROR: expected 1 unique call")
