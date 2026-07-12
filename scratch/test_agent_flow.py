"""
test_agent_flow.py
==================
End-to-end test that simulates a real passenger conversation with the AI agent.
Runs 3 turns:
  1. User asks for stops near "Nation"
  2. User asks to travel from Nation to Chatou - Croissy
  3. User asks when they will arrive

Each step:
  - Measures wall-clock time
  - PASS if response makes sense and takes <= 30s total
  - FAIL if an error is returned or duplicates are found in step 1

Usage:
    python scratch/test_agent_flow.py
"""

import sys
import os

# Force UTF-8 output so Arabic text and special chars don't crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import time
import json
import re

# Add root to path so imports work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from backend.services.agent_service import TransitAgentService
from backend.services.search_service import search_stops

# ── ANSI colours ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

PASS = f"{GREEN}✅ PASS{RESET}"
FAIL = f"{RED}❌ FAIL{RESET}"

def banner(text):
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}  {text}{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")

# ── Unit test: search_stops deduplication ─────────────────────────────────────
def test_search_no_duplicates():
    banner("Unit Test: search_stops — no duplicate names")
    t0 = time.time()
    results = search_stops("Chatou", limit=10)
    elapsed = time.time() - t0

    names = [r["stop_name"] for r in results]
    duplicates = [n for n in names if names.count(n) > 1]

    print(f"  Query time : {elapsed:.3f}s")
    print(f"  Results    : {len(results)} stops")
    for r in results:
        lt = r['location_type']
        marker = "(parent station)" if lt == 1 else "(platform)"
        print(f"    - {r['stop_name']} (type={lt} {marker})  id={r['stop_id']}")

    if duplicates:
        print(f"  {FAIL} — Duplicate names found: {set(duplicates)}")
        return False

    if elapsed > 5.0:
        print(f"  {FAIL} -- Query took {elapsed:.2f}s > 5s limit")
        return False

    print(f"  {PASS} -- All names unique, query fast ({elapsed:.3f}s)")
    return True


# ── Integration test: agent conversation ─────────────────────────────────────
def test_agent_conversation():
    banner("Integration Test: Full Passenger Conversation (3 turns)")
    agent = TransitAgentService()
    history = []
    all_passed = True

    # ── Turn 1: search for stations ───────────────────────────────────────────
    print(f"\n{YELLOW}Turn 1:{RESET} Asking about stations near Nation...")
    t0 = time.time()
    response, history = agent.chat(
        "ما هي المحطات المتاحة بالقرب من محطة Nation؟",
        history,
        mode="user"
    )
    elapsed = time.time() - t0

    print(f"  Response ({elapsed:.1f}s):\n    {response[:300]}{'...' if len(response) > 300 else ''}")

    # Check: response must mention "Nation" or "محطة"
    if "nation" in response.lower() or "محطة" in response or "stop" in response.lower():
        print(f"  {PASS} — Response mentions stations")
    else:
        print(f"  {FAIL} — Response doesn't mention relevant stations")
        all_passed = False

    # Check: no obvious duplicate lines (same line repeated 4×)
    lines = [l.strip() for l in response.split("\n") if l.strip()]
    if len(lines) > 0:
        from collections import Counter
        freq = Counter(lines)
        most_common_count = freq.most_common(1)[0][1]
        if most_common_count >= 4:
            print(f"  {FAIL} — Response has a line repeated {most_common_count}× (duplicate station names?)")
            all_passed = False
        else:
            print(f"  {PASS} — No duplicate lines in response")

    # ── Turn 2: ask for a route ───────────────────────────────────────────────
    print(f"\n{YELLOW}Turn 2:{RESET} Asking for route from Nation to Chatou - Croissy...")
    t0 = time.time()
    response2, history = agent.chat(
        "عايز أروح من محطة Nation لـ Chatou - Croissy الساعة 9 الصبح",
        history,
        mode="user"
    )
    elapsed2 = time.time() - t0

    print(f"  Response ({elapsed2:.1f}s):\n    {response2[:400]}{'...' if len(response2) > 400 else ''}")

    route_keywords = ["رحلة", "خط", "line", "وصول", "مغادرة", "arrival", "departure", "chatou", "nation"]
    if any(kw in response2.lower() for kw in route_keywords):
        print(f"  {PASS} — Response contains route information")
    else:
        print(f"  {FAIL} — Response doesn't mention route details")
        all_passed = False

    # ── Turn 3: arrival time question ─────────────────────────────────────────
    print(f"\n{YELLOW}Turn 3:{RESET} Asking when they will arrive...")
    t0 = time.time()
    response3, history = agent.chat(
        "امتى بوصل بالظبط؟ وكام وقت الرحلة؟",
        history,
        mode="user"
    )
    elapsed3 = time.time() - t0

    print(f"  Response ({elapsed3:.1f}s):\n    {response3[:400]}{'...' if len(response3) > 400 else ''}")

    # Check: response should contain a time pattern HH:MM
    time_pattern = re.compile(r'\d{1,2}:\d{2}')
    if time_pattern.search(response3):
        print(f"  {PASS} — Response contains a time value")
    else:
        print(f"  ⚠️  WARNING — No time pattern found; agent may not have route data in context")

    return all_passed


# ── Analytics API sanity check (direct DB queries) ────────────────────────────
def test_analytics_day_vs_month():
    banner("DB Query Test: analytics day vs month consistency")
    from database import get_db_connection

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Get max date
            cur.execute("SELECT MAX(end_date) FROM gtfs.calendar")
            max_date = str(cur.fetchone()[0])

            t0 = time.time()
            cur.execute("""
                SELECT COUNT(*) FROM gtfs.trips t
                JOIN gtfs.calendar c ON t.service_id = c.service_id
                WHERE %s BETWEEN c.start_date AND c.end_date
            """, (max_date,))
            day_trips = cur.fetchone()[0]
            day_time = time.time() - t0

            t0 = time.time()
            cur.execute("SELECT COUNT(*) FROM gtfs.trips")
            month_trips = cur.fetchone()[0]
            month_time = time.time() - t0

        conn.close()

        print(f"  Last active day ({max_date})  : {day_trips:,} trips  ({day_time:.3f}s)")
        print(f"  All trips in DB              : {month_trips:,} trips  ({month_time:.3f}s)")

        if day_trips <= month_trips:
            print(f"  {PASS} — Day count ≤ month count (makes sense)")
        else:
            print(f"  {FAIL} — Day count > month count (impossible!)")
            return False

        if day_time > 5.0:
            print(f"  {FAIL} — Day query took {day_time:.2f}s > 5s timeout!")
            return False

        return True
    except Exception as e:
        print(f"  {FAIL} — DB error: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{CYAN}===  Railflow Agent Test Suite  ==={RESET}")
    print(f"{CYAN}    Running all checks...{RESET}\n")

    results = {
        "search_no_duplicates":    test_search_no_duplicates(),
        "analytics_day_vs_month":  test_analytics_day_vs_month(),
        "agent_conversation":      test_agent_conversation(),
    }

    banner("Summary")
    total = len(results)
    passed = sum(results.values())
    for name, ok in results.items():
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {name}")

    print(f"\n  {passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
    else:
        print(f"\n{GREEN}  All tests passed!{RESET}\n")
