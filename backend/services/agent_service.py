import json
from typing import List, Dict, Any, Tuple
from database import get_db_connection
from backend.utils.llm import GroqClient
from backend.services.search_service import search_stops
from backend.services.routing_service import find_routes
from backend.services.departures_service import get_departures, get_connection

class TransitAgentService:
    """Service to coordinate the AI Transit Agent chat loop and tools calling."""
    def __init__(self):
        self.client = GroqClient()
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_stations",
                    "description": (
                        "Search for transit stations/stops by name. "
                        "Use this ONLY when the user asks generic search terms or you don't know the station name. "
                        "Do NOT call this if the user already named the station in their question (e.g. 'Chatou - Croissy' or 'Nation') — "
                        "instead, call get_departures or get_connection directly."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Part of the station name to search for (e.g. 'Nation', 'Chatou', 'Halles')."
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results. Default is 8."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_departures",
                    "description": (
                        "Returns the next departures FROM a station. "
                        "Accepts human-readable station names directly (e.g. 'Chatou - Croissy', 'Nation'). "
                        "Use this when the user asks 'what trains leave from X', 'departures from Nation', 'what is the destination of trips passing through X', or 'how many trains go from X'. "
                        "Do NOT call search_stations first if the station name is already in the user's question."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "stop_query": {
                                "type": "string",
                                "description": "Station name or stop ID to get departures from (e.g. 'Nation', 'Chatou - Croissy')."
                            },
                            "after_time": {
                                "type": "string",
                                "description": "Only show trains departing at or after this time. Format HH:MM:SS. Optional, defaults to now."
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of departures to return. Default 10."
                            }
                        },
                        "required": ["stop_query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_connection",
                    "description": (
                        "Finds transit connections (direct and 1-transfer) between two stations. "
                        "Accepts human-readable station names directly. You do NOT need to call search_stations first. "
                        "Use this when the user asks 'how do I get from A to B', 'route from X to Y', or 'when does the train arrive at Z'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_query": {
                                "type": "string",
                                "description": "Departure station name or stop ID."
                            },
                            "to_query": {
                                "type": "string",
                                "description": "Destination station name or stop ID."
                            },
                            "after_time": {
                                "type": "string",
                                "description": "Earliest departure time in HH:MM:SS. Optional, defaults to now."
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max number of connection options to return. Default 5."
                            }
                        },
                        "required": ["from_query", "to_query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_readonly_sql",
                    "description": (
                        "ANALYST ONLY: Executes a custom SELECT query on the GTFS database "
                        "for statistics and reporting. Use ONLY for counting rows, aggregate "
                        "statistics, or data not covered by the other tools. "
                        "Do NOT use for station search or routing — use search_stations, "
                        "get_departures, or get_connection instead."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql_query": {
                                "type": "string",
                                "description": "A read-only SELECT SQL query on tables under the 'gtfs' schema."
                            }
                        },
                        "required": ["sql_query"]
                    }
                }
            }
        ]
        
        # ── User-facing assistant prompt ──────────────────────────────────────
        self.user_system_prompt = (
            "تنبيه هام جداً: يجب كتابة أسماء المحطات بالحروف اللاتينية الإنجليزية الأصلية كما هي في قاعدة البيانات (مثل Gare du Nord, La Défense, Châtelet - Les Halles). يمنع منعاً باتاً ترجمتها أو كتابة نطقها بالحروف العربية (لا تكتب 'لا ديفينس' ولا تكتب 'غار دو نور'). اكتب أسماء المحطات باللاتينية دائماً حتى لو كان بقية الرد باللغة العربية.\n"
            "CRITICAL RULE #1: NEVER translate or transliterate station names into Arabic characters (e.g., do NOT write 'شاتليه' or 'لا ديفينس'). ALWAYS output the station names exactly in their original Latin spelling (e.g. 'Châtelet - Les Halles', 'La Défense', 'Gare du Nord', 'Nation', 'Chatou - Croissy') as returned by the tools, even when the rest of your response is in Arabic.\n\n"
            "You are a friendly, expert AI Transit Assistant for a public transport network (Paris RER/Metro).\n"
            "You help passengers plan journeys, find stations, and check departure schedules.\n\n"
            "AVAILABLE TOOLS (use ONLY these — call ONE tool per response):\n"
            "1. search_stations(query, limit)\n"
            "   → Use ONLY when the user asks generic terms or searches for a name. DO NOT use if the user already named the station in their question.\n"
            "2. get_departures(stop_query, after_time, limit)\n"
            "   → Use when: user asks 'what trains leave from X', 'departures from Nation', 'what is the destination of trips passing through X', etc. Call this directly using the station name.\n"
            "3. get_connection(from_query, to_query, after_time, limit)\n"
            "   → Use when: user asks 'how do I get from A to B', 'route from X to Y', 'when do I arrive'. Call this directly using the station names.\n\n"
            "STRICT RULES:\n"
            "- Call EXACTLY ONE tool per response. Never call multiple tools at once.\n"
            "- After receiving tool results, respond IMMEDIATELY in natural language. Do NOT call another tool unless the user asks a new question.\n"
            "- NEVER call run_readonly_sql. It is disabled for user mode.\n"
            "- NEVER expose tool names, SQL, or database terms to the user.\n"
            "- If a station is not found, tell the user politely and suggest they rephrase the name.\n"
            "- DESTINATION RULE: When the user asks about the final arrival stations or destinations of trips passing through station X (e.g. 'ما هي محطة الوصول للرحلات التي تمر بـ Chatou - Croissy'), look at the 'direction' field of the departures list. Those are the final destinations of the trips (e.g. Marne-la-Vallée Chessy, Saint-Germain-en-Laye). Do NOT say the arrival station is station X itself.\n"
            "- CAPPED LIMITS: Note that tools are programmatically capped at a maximum of 15 results for network efficiency. If a tool returns fewer results than you requested (e.g. you asked for 100 but got 15), this is normal and represents a complete and successful response. Do NOT apologize or say you couldn't find them; just present the returned stations directly as the main stations.\n"
        )




        # ── Analyst prompt ────────────────────────────────────────────────────
        self.analyst_system_prompt = (
            "تنبيه هام جداً: يجب كتابة أسماء المحطات بالحروف اللاتينية الإنجليزية الأصلية كما هي في قاعدة البيانات (مثل Gare du Nord, La Défense, Châtelet - Les Halles). يمنع منعاً باتاً ترجمتها أو كتابة نطقها بالحروف العربية (لا تكتب 'لا ديفينس' ولا تكتب 'غار دو نور'). اكتب أسماء المحطات باللاتينية دائماً حتى لو كان بقية الرد باللغة العربية.\n"
            "CRITICAL RULE #1: NEVER translate or transliterate station names into Arabic characters (e.g., do NOT write 'شاتليه' or 'لا ديفينس'). ALWAYS output the station names exactly in their original Latin spelling (e.g. 'Châtelet - Les Halles', 'La Défense', 'Gare du Nord', 'Nation', 'Chatou - Croissy') as returned by the tools, even when the rest of your response is in Arabic.\n\n"
            "You are a public transit Operations & Performance Analyst AI for the Paris Transit / RER Network.\n"
            "The database contains actual GTFS data for Paris RER lines (e.g. Line A, Line B, Line D, Line E) and stations (e.g. Nation, Chatou - Croissy, Gare de Lyon, La Défense, Gare du Nord).\n"
            "Your goal: analyze the Paris transit network and produce a structured report.\n\n"
            "AVAILABLE TOOLS (call ONE at a time):\n"
            "1. search_stations(query)          → find a station in Paris by name\n"
            "2. get_departures(stop_query)       → departures from a Paris station today\n"
            "3. get_connection(from_query, to_query) → connections between Paris stations\n"
            "4. run_readonly_sql(sql_query)      → custom SELECT on the gtfs schema\n\n"
            "CRITICAL DIRECTIVE:\n"
            "- When asked to write a general operational report (e.g. 'اكتب تقريراً تشغيلياً'), you MUST query the database for actual statistics (like the busiest stations, total trips, or route stats on the latest day) using run_readonly_sql.\n"
            "- DO NOT hallucinate station names from outside France (like Egyptian landmarks, Cairo Metro, or 'ميدان التحرير'). If you search for cairo/egyptian landmarks, they will return empty results. Search only for Paris stations.\n\n"
            "SQL RULES (for run_readonly_sql only):\n"
            "  * Always prefix tables: gtfs.stops, gtfs.routes, gtfs.trips, gtfs.stop_times, gtfs.calendar.\n"
            "  * To filter by active date: JOIN gtfs.calendar c ON t.service_id=c.service_id WHERE (SELECT MAX(end_date) FROM gtfs.calendar) BETWEEN c.start_date AND c.end_date\n"
            "  * To get stop names from stop_times: JOIN gtfs.stops s ON st.stop_id=s.stop_id (stop_times has NO stop_name column).\n"
            "  * Use only English aliases in SQL (no Arabic words in aliases).\n"
            "  * Call run_readonly_sql ONCE with a single complete query. Do NOT repeat the same query.\n\n"
            "STRICT RULES:\n"
            "- Call EXACTLY ONE tool per response turn.\n"
            "- After receiving results, write your report IMMEDIATELY. Do NOT keep calling tools.\n"
            "- Structure your final response as:\n"
            "  1. التقرير التحليلي (Analytical Report): data-backed findings\n"
            "  2. التوصيات (Recommendations): concrete, actionable suggestions for Paris transit quality\n"
            "- Respond in Arabic unless the user writes in English.\n"
        )





    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Executes the tool by name and returns string output."""
        print(f"Executing tool {name} with arguments: {args}")
        try:
            if name == "search_stations":
                # New dedicated station search tool (capped at max 15 to prevent Groq 413 token overflow)
                query = args.get("query", "")
                limit = min(int(args.get("limit", 8) or 8), 15)
                results = search_stops(query, limit)
                return json.dumps(results, ensure_ascii=False)

            elif name == "get_departures":
                # New departures tool (capped at max 15)
                stop_query   = args.get("stop_query", "")
                after_time   = args.get("after_time")
                limit        = min(int(args.get("limit", 10) or 10), 15)
                result = get_departures(stop_query, after_time, limit)
                return json.dumps(result, default=str, ensure_ascii=False)

            elif name == "get_connection":
                # New connection/routing tool (capped at max 5)
                from_query  = args.get("from_query", "")
                to_query    = args.get("to_query", "")
                after_time  = args.get("after_time")
                limit       = min(int(args.get("limit", 5) or 5), 5)
                result = get_connection(from_query, to_query, after_time, limit)
                return json.dumps(result, default=str, ensure_ascii=False)

            elif name in ("search_stops", "find_route"):
                # Legacy tools kept for backward compatibility
                if name == "search_stops":
                    query = args.get("query")
                    limit = min(int(args.get("limit", 5) or 5), 15)
                    results = search_stops(query, limit)
                    return json.dumps(results, ensure_ascii=False)

                else:
                    start_stop_id  = args.get("start_stop_id")
                    end_stop_id    = args.get("end_stop_id")
                    departure_time = args.get("departure_time")
                    results = find_routes(start_stop_id, end_stop_id, departure_time)
                    return json.dumps(results, ensure_ascii=False)

            elif name == "run_readonly_sql":
                sql_query = args.get("sql_query", "")
                normalized = sql_query.strip().lower()
                
                if not normalized.startswith("select"):
                    return "Error: Only SELECT queries are allowed."
                
                forbidden_keywords = ["insert", "update", "delete", "drop", "truncate", "alter", "create"]
                if any(kw in normalized for kw in forbidden_keywords):
                    return "Error: Modifying keywords are forbidden. Only read-only SELECT operations are allowed."
                
                conn = get_db_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute(sql_query)
                        rows = cur.fetchmany(50)
                        if cur.description:
                            colnames = [desc[0] for desc in cur.description]
                            results = [dict(zip(colnames, r)) for r in rows]
                            return json.dumps(results, default=str, ensure_ascii=False)
                        return "Command completed successfully (no return columns)."
                except Exception as db_err:
                    return f"Database Error: {str(db_err)}"
                finally:
                    conn.close()
            else:
                return f"Error: Tool '{name}' not found."
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    def _get_analyst_data_prompt(self) -> str:
        """Runs fast Python DB queries to extract core statistics and shapes the analyst prompt."""
        import datetime
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # 1. Total trips & max date
                cur.execute("""
                    SELECT COUNT(*), MAX(c.end_date)
                    FROM gtfs.trips t
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    WHERE (SELECT MAX(end_date) FROM gtfs.calendar) BETWEEN c.start_date AND c.end_date
                """)
                tot_row = cur.fetchone()
                tot = tot_row[0] if tot_row and tot_row[0] is not None else 0
                mx_dt = str(tot_row[1]) if tot_row and tot_row[1] is not None else "2026-06-24"
                
                # 2. Busiest stations (grouped by parent station, ordered by departures)
                cur.execute("""
                    SELECT COALESCE(p.stop_name, s.stop_name) as main_station, COUNT(*) as num_departures
                    FROM gtfs.stop_times st
                    JOIN gtfs.stops s ON st.stop_id = s.stop_id
                    LEFT JOIN gtfs.stops p ON s.parent_station = p.stop_id
                    JOIN gtfs.trips t ON st.trip_id = t.trip_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    WHERE %s BETWEEN c.start_date AND c.end_date
                    GROUP BY main_station
                    ORDER BY num_departures DESC
                    LIMIT 10
                """, (mx_dt,))
                stations = cur.fetchall()
                
                # 3. Busiest routes
                cur.execute("""
                    SELECT COALESCE(r.route_short_name, r.route_long_name) as route_name, COUNT(t.trip_id) as num_trips
                    FROM gtfs.trips t
                    JOIN gtfs.routes r ON t.route_id = r.route_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    WHERE %s BETWEEN c.start_date AND c.end_date
                    GROUP BY route_name
                    ORDER BY num_trips DESC
                    LIMIT 5
                """, (mx_dt,))
                routes = cur.fetchall()
                
                # 4. Hourly departures distribution
                cur.execute("""
                    SELECT SUBSTRING(st.departure_time, 1, 2) as hr, COUNT(*) as num_departures
                    FROM gtfs.stop_times st
                    JOIN gtfs.trips t ON st.trip_id = t.trip_id
                    JOIN gtfs.calendar c ON t.service_id = c.service_id
                    WHERE %s BETWEEN c.start_date AND c.end_date
                    GROUP BY hr
                    ORDER BY hr
                """, (mx_dt,))
                hours = cur.fetchall()
                
            prompt = (
                f"Here is the pre-queried transit database operational data for the latest active date ({mx_dt}):\n\n"
                f"- Latest Active Date: {mx_dt}\n"
                f"- Total Scheduled Trips: {tot:,} trips\n\n"
                f"- Top 10 Busiest Stations (by departures count):\n"
            )
            for s in stations:
                prompt += f"  * {s[0]}: {s[1]:,} departures\n"
                
            prompt += f"\n- Top 5 Busiest Routes (by trips count):\n"
            for r in routes:
                prompt += f"  * Line {r[0]}: {r[1]:,} trips\n"
                
            prompt += f"\n- Departures Hourly Distribution:\n"
            for h in hours:
                prompt += f"  * Hour {h[0]}:00: {h[1]:,} departures\n"
                
            prompt += (
                "\nINSTRUCTIONS:\n"
                "Write a highly detailed, clear, comprehensive, and detail-rich operational performance analysis report (التقرير التحليلي) "
                "and actionable optimization recommendations (التوصيات والنصائح) in Arabic.\n"
                "DO NOT call any database tools (such as run_readonly_sql or search_stations). Use ONLY the actual data provided above.\n"
                "NEVER translate or transliterate the station names to Arabic characters (e.g. write 'Châtelet - Les Halles', 'La Défense', 'Gare du Nord', 'Nation', 'Chatou - Croissy' exactly). Keep them in their original Latin script, even inside Arabic text."
            )
            return prompt
        except Exception as e:
            return f"Error gathering operational data: {str(e)}"
        finally:
            conn.close()

    def chat(self, user_message: str, history: List[Dict[str, Any]] = None, mode: str = "user") -> Tuple[str, List[Dict[str, Any]]]:
        """Runs the conversational agent loop with Groq. Returns (assistant_response, updated_history)."""
        if history is None:
            history = []
            
        # Select system prompt based on mode
        sys_prompt = self.analyst_system_prompt if mode == "analyst" else self.user_system_prompt
        messages = [{"role": "system", "content": sys_prompt}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
            
        # Check if analyst mode wants to generate the operational report
        is_report_request = mode == "analyst" and any(k in user_message for k in ("تقرير", "تشغيلي", "احصائيات", "تحليل"))
        
        if is_report_request:
            # Pre-query data and replace the model prompt message with the rich data prompt
            llm_message = self._get_analyst_data_prompt()
        else:
            llm_message = user_message

        messages.append({"role": "user", "content": llm_message})
        
        # Add original user message to history
        history.append({"role": "user", "content": user_message})
        
        # ── Safety constants ───────────────────────────────────────────────────
        MAX_TURNS        = 6   # max agent loop iterations
        MAX_TOOL_CALLS   = 5   # max unique tool calls per single LLM response
        MAX_MSG_CHARS    = 18_000  # approx char budget before trimming old messages
        
        def _trim_messages(msgs):
            """Drop old tool-result messages if context is getting too large."""
            total = sum(len(str(m.get("content", ""))) for m in msgs)
            while total > MAX_MSG_CHARS and len(msgs) > 2:
                # Remove the oldest non-system, non-last-user message
                for i in range(1, len(msgs) - 1):
                    if msgs[i].get("role") in ("tool", "assistant") and msgs[i] is not msgs[-1]:
                        removed = msgs.pop(i)
                        total -= len(str(removed.get("content", "")))
                        break
                else:
                    break  # nothing left to remove safely
            return msgs

        # Agent execution loop
        for turn in range(MAX_TURNS):
            if turn > 0:
                import time
                time.sleep(1.2)  # Respect Groq rate limits (TPM)

            # Guard: trim context before every Groq call
            messages = _trim_messages(messages)

            response = self.client.chat_completion(messages, tools=self.tools)
            choice = response["choices"][0]["message"]
            print(f"\n--- Groq LLM Response (Turn {turn}) ---")
            print(json.dumps(choice, indent=2, ensure_ascii=False))
            
            # Check if model wants to call a tool natively
            tool_calls = choice.get("tool_calls")
            
            # Check if model generated a text-based tool call fallback
            content = choice.get("content") or ""
            text_tool_match = None
            func_name = None
            func_args = None
            
            if not tool_calls:
                import re
                if "run_readonly_sql" in content and "<sql_query>" in content:
                    sql_match = re.search(r"<sql_query>(.*?)</sql_query>", content, re.DOTALL)
                    if sql_match:
                        func_name = "run_readonly_sql"
                        func_args = {"sql_query": sql_match.group(1).strip()}
                        text_tool_match = True
                elif "<function" in content or "<function=" in content:
                    # Match <function=name>args</function> or <function name>args</function>
                    func_match = re.search(r"<function[= ](\w+)[^\w]*>(.*?)(?:</function>|$)", content, re.DOTALL)
                    if func_match:
                        func_name = func_match.group(1).strip()
                        raw_args = func_match.group(2).strip()
                        
                        # Strip trailing function tags if the closing tag wasn't fully matched
                        if raw_args.endswith("</function>"):
                            raw_args = raw_args[:-11].strip()
                            
                        # Try parsing as JSON object
                        try:
                            func_args = json.loads(raw_args)
                            if isinstance(func_args, dict):
                                text_tool_match = True
                        except Exception:
                            # Not a JSON object. Check if it's a quoted or raw string and map to schema
                            clean_val = raw_args.strip('\'" \n\r')
                            if func_name == "get_departures":
                                func_args = {"stop_query": clean_val}
                                text_tool_match = True
                            elif func_name == "search_stations":
                                func_args = {"query": clean_val}
                                text_tool_match = True
                            elif func_name == "run_readonly_sql":
                                func_args = {"sql_query": clean_val}
                                text_tool_match = True
                            elif func_name == "get_connection":
                                # If it's a comma-separated values, try parsing them
                                parts = [p.strip('\'" ') for p in clean_val.split(",")]
                                if len(parts) >= 2:
                                    func_args = {"from_query": parts[0], "to_query": parts[1]}
                                    text_tool_match = True


            if tool_calls:
                # ── DEDUPLICATION: collapse identical (name, args) pairs ────────
                # The LLM sometimes emits 50+ copies of the same call.
                # We keep only the FIRST occurrence of each unique (name, args) pair
                # and cap the total at MAX_TOOL_CALLS so the context never explodes.
                seen_keys = set()
                unique_calls = []
                for tc in tool_calls:
                    key = (tc["function"]["name"], tc["function"]["arguments"])
                    if key not in seen_keys:
                        seen_keys.add(key)
                        unique_calls.append(tc)
                    if len(unique_calls) >= MAX_TOOL_CALLS:
                        break

                if len(unique_calls) < len(tool_calls):
                    dropped = len(tool_calls) - len(unique_calls)
                    print(f"[DEDUP] Dropped {dropped} duplicate/excess tool calls. Keeping {len(unique_calls)}.")

                # Rebuild choice to only reference the unique tool calls,
                # so Groq receives a valid message with matching tool_call_ids.
                deduped_choice = dict(choice)
                deduped_choice["tool_calls"] = unique_calls
                messages.append(deduped_choice)

                # Execute each unique tool call and collect results
                tool_cache: Dict[tuple, str] = {}
                for tc in unique_calls:
                    tc_id    = tc["id"]
                    f_name   = tc["function"]["name"]
                    f_args_s = tc["function"]["arguments"]
                    cache_key = (f_name, f_args_s)

                    if cache_key in tool_cache:
                        tool_output = tool_cache[cache_key]
                    else:
                        try:
                            f_args = json.loads(f_args_s)
                        except Exception:
                            f_args = {}
                        tool_output = self._execute_tool(f_name, f_args)
                        print(f"Tool {f_name} output: {tool_output[:300]}{'...' if len(tool_output) > 300 else ''}")
                        tool_cache[cache_key] = tool_output

                    messages.append({
                        "role":         "tool",
                        "tool_call_id": tc_id,
                        "name":         f_name,
                        "content":      tool_output
                    })

                # Continue loop to send tool outputs back to the model
                continue
                
            elif text_tool_match:
                # Process the text-based tool call fallback
                tool_output = self._execute_tool(func_name, func_args)
                print(f"Parsed Text-Tool {func_name} output: {tool_output[:300]}")
                
                messages.append(choice)
                messages.append({
                    "role":    "user",
                    "content": f"[System: Output for tool '{func_name}': {tool_output}]"
                })
                continue
                
            else:
                # Final text response generated — return to caller
                final_content = content
                
                # Programmatic post-processing: Guarantee station names remain in Latin/original spelling
                translation_map = {
                    # 1. Stade de France
                    "ستاد فرانس سان دينيس": "Stade de France Saint-Denis",
                    "ستاد فرانس سان ديني": "Stade de France Saint-Denis",
                    "ستاد فرانس": "Stade de France Saint-Denis",
                    
                    # 2. Châtelet - Les Halles
                    "شاتليه - ليس هالز": "Châtelet - Les Halles",
                    "شاتليه ليس هالز": "Châtelet - Les Halles",
                    "شاتليه - ليس هال": "Châtelet - Les Halles",
                    "شاتليه": "Châtelet - Les Halles",
                    
                    # 3. Saint-Michel Notre-Dame
                    "سانت ميشيل نوتر دام": "Saint-Michel Notre-Dame",
                    "سانت ميشيل نوتردام": "Saint-Michel Notre-Dame",
                    "سانت ميشيل نوف ديم": "Saint-Michel Notre-Dame",
                    "سان ميشيل نوتر دام": "Saint-Michel Notre-Dame",
                    "سان ميشيل نوتردام": "Saint-Michel Notre-Dame",
                    "سانت ميشيل": "Saint-Michel Notre-Dame",
                    "سان ميشيل": "Saint-Michel Notre-Dame",
                    "نوتر دام": "Saint-Michel Notre-Dame",
                    "نوتردام": "Saint-Michel Notre-Dame",
                    "نوف ديم": "Saint-Michel Notre-Dame",
                    
                    # 4. Aulnay-sous-Bois
                    "أولناي سو بواس": "Aulnay-sous-Bois",
                    "أولناي سو بوا": "Aulnay-sous-Bois",
                    "اويناي سو بواس": "Aulnay-sous-Bois",
                    "اويناي سو بوا": "Aulnay-sous-Bois",
                    "أولناي": "Aulnay-sous-Bois",
                    "اويناي": "Aulnay-sous-Bois",
                    
                    # 5. Gare Saint-Lazare
                    "غار سان لازار": "Gare Saint-Lazare",
                    "جار سان لازار": "Gare Saint-Lazare",
                    
                    # 6. Gare du Nord
                    "غار دو نورد": "Gare du Nord",
                    "غار دو نور": "Gare du Nord",
                    "جار دو نور": "Gare du Nord",
                    
                    # 7. Gare de Lyon
                    "جار دو ليون": "Gare de Lyon",
                    "غار ليون": "Gare de Lyon",
                    
                    # 8. La Défense
                    "لا ديفينس": "La Défense",
                    "لا ديفنس": "La Défense",
                    
                    # 9. Chatou - Croissy
                    "شاتوه - كروازي": "Chatou - Croissy",
                    "شاتو - كروازي": "Chatou - Croissy",
                    "شاتوه": "Chatou - Croissy",
                    "شاتو": "Chatou - Croissy",
                    
                    # 10. Charles de Gaulle - Étoile
                    "شارل ديغول - إتوال": "Charles de Gaulle - Étoile",
                    
                    # 11. Nanterre-Université
                    "نانتير - أونيفرسيتيه": "Nanterre-Université",
                    "نانتير": "Nanterre-Université",
                    
                    # 12. Others
                    "ناتيون": "Nation",
                    "ناسيون": "Nation",
                    "فينسين": "Vincennes",
                    "فانسن": "Vincennes",
                    "سارتوفيل": "Sartrouville",
                    "سارتروفيل": "Sartrouville"
                }


                
                for ar_name, lat_name in translation_map.items():
                    # Replace both with and without Al- (الـ) prefix
                    final_content = final_content.replace(ar_name, lat_name)
                    final_content = final_content.replace("ال" + ar_name, lat_name)
                    final_content = final_content.replace("ل" + ar_name, lat_name)

                history.append({"role": "assistant", "content": final_content})
                return final_content, history
                
        return "عذراً، واجهت صعوبة في معالجة طلبك. يرجى المحاولة مرة أخرى.", history


