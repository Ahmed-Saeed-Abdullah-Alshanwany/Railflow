import json
from typing import List, Dict, Any, Tuple
from database import get_db_connection
from backend.utils.llm import GroqClient
from backend.services.search_service import search_stops
from backend.services.routing_service import find_routes

class TransitAgentService:
    """Service to coordinate the AI Transit Agent chat loop and tools calling."""
    def __init__(self):
        self.client = GroqClient()
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_stops",
                    "description": "Fuzzy searches stops in the GTFS database by their name (e.g. 'Chatou', 'Nation') and returns their stop_id and coordinates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query (station or stop name)."
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return. Default is 5."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_route",
                    "description": "Finds route schedule options between a start stop ID and end stop ID departing after a specific time.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_stop_id": {
                                "type": "string",
                                "description": "The stop ID of the departure station."
                            },
                            "end_stop_id": {
                                "type": "string",
                                "description": "The stop ID of the destination station."
                            },
                            "departure_time": {
                                "type": "string",
                                "description": "Departure time in HH:MM:SS format (e.g., '09:00:00' or '18:30:00'). Optional; defaults to current time."
                            }
                        },
                        "required": ["start_stop_id", "end_stop_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_readonly_sql",
                    "description": "Executes a SELECT query on the GTFS database schema. The query must only contain SELECT statements on tables under the 'gtfs' schema (like 'gtfs.agency', 'gtfs.routes', 'gtfs.stops', 'gtfs.stop_times', 'gtfs.trips', 'gtfs.calendar'). Use this to count rows, find names, or perform custom statistics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql_query": {
                                "type": "string",
                                "description": "The read-only SELECT SQL query to execute."
                            }
                        },
                        "required": ["sql_query"]
                    }
                }
            }
        ]
        
        self.user_system_prompt = (
            "You are a helpful, expert AI Transit Assistant for the public transport network. "
            "You have access to a PostgreSQL database under the 'gtfs' schema. Use the provided tools (search_stops, find_route, run_readonly_sql) to interact with the database.\n\n"
            "Database Schema Info:\n"
            "- gtfs.agency (agency_id, agency_name, agency_url, agency_timezone)\n"
            "- gtfs.stops (stop_id, stop_name, stop_lon, stop_lat, location_type, parent_station)\n"
            "- gtfs.routes (route_id, agency_id, route_short_name, route_long_name, route_type)\n"
            "- gtfs.trips (route_id, service_id, trip_id, trip_headsign)\n"
            "- gtfs.stop_times (trip_id, arrival_time, departure_time, stop_id, stop_sequence)\n"
            "- gtfs.calendar (service_id, start_date, end_date)\n"
            "- gtfs.transfers (from_stop_id, to_stop_id, transfer_type, min_transfer_time)\n\n"
            "INSTRUCTIONS:\n"
            "- Always use the native function calling feature to invoke tools. Never output raw text-based function tags in your text response.\n"
            "- To search for a specific stop/station by name or fuzzy query, call 'search_stops'. For general lists, counts, or statistics of stops, use 'run_readonly_sql' instead.\n"
            "- To plan routes, call 'find_route'. You can pass EITHER exact database IDs (like 'IDFM:22072') OR human-readable stop names (like 'Nation' or 'Chatou') as start_stop_id and end_stop_id, and they will be resolved automatically.\n"
            "- To run custom queries/statistics, write a read-only SELECT SQL statement and call 'run_readonly_sql'.\n"
            "SQL QUERY GUIDELINES:\n"
            "  * To get stop names in stop_times queries, you MUST join gtfs.stop_times with gtfs.stops on stop_id (e.g., JOIN gtfs.stops s ON st.stop_id = s.stop_id) because stop_times does NOT have a stop_name column.\n"
            "  * To filter trips active on a date, join gtfs.trips (t) and gtfs.calendar (c) on service_id, and check: (SELECT MAX(end_date) FROM gtfs.calendar) BETWEEN c.start_date AND c.end_date. Do NOT multiply date by interval or compare departure_time (time string) directly to end_date (date).\n"
            "  * ALWAYS write SQL aliases using plain English alphanumeric characters (e.g., 'as num_trips'). Never write Arabic words or spaces in SQL aliases, as they cause database syntax errors.\n"
            "- By default, when asked about busiest stations, lines, schedules, or statistics, ALWAYS find the latest active date in the database first (e.g., SELECT MAX(end_date) FROM gtfs.calendar) and filter all your queries to only count trips active on that specific date, rather than counting all historical database rows. State this date clearly in your response.\n"
            "- When presenting database query results or route results, ALWAYS list the actual names, values, and details clearly in your final response text.\n"
            "- Respond in the user's language (e.g. Arabic or English)."
        )

        self.analyst_system_prompt = (
            "You are a high-level public transit Operations & Performance Analyst AI Agent. "
            "Your core objective is to analyze the transit network to maximize throughput, optimize schedule efficiency, find service gaps, and improve overall service quality.\n\n"
            "You have access to a PostgreSQL database under the 'gtfs' schema. Use the provided tools (search_stops, find_route, run_readonly_sql) to gather network statistics.\n\n"
            "Database Schema Info:\n"
            "- gtfs.agency (agency_id, agency_name, agency_url, agency_timezone)\n"
            "- gtfs.stops (stop_id, stop_name, stop_lon, stop_lat, location_type, parent_station)\n"
            "- gtfs.routes (route_id, agency_id, route_short_name, route_long_name, route_type)\n"
            "- gtfs.trips (route_id, service_id, trip_id, trip_headsign)\n"
            "- gtfs.stop_times (trip_id, arrival_time, departure_time, stop_id, stop_sequence)\n"
            "- gtfs.calendar (service_id, start_date, end_date)\n"
            "- gtfs.transfers (from_stop_id, to_stop_id, transfer_type, min_transfer_time)\n\n"
            "INSTRUCTIONS & RULES:\n"
            "- Always use the native function calling feature to invoke tools. Never output raw text-based function tags in your text response.\n"
            "- To plan routes, call 'find_route'. You can pass EITHER exact database IDs (like 'IDFM:22072') OR human-readable stop names (like 'Nation' or 'Chatou') as start_stop_id and end_stop_id, and they will be resolved automatically.\n"
            "SQL QUERY GUIDELINES:\n"
            "  * To get stop names in stop_times queries, you MUST join gtfs.stop_times with gtfs.stops on stop_id (e.g., JOIN gtfs.stops s ON st.stop_id = s.stop_id) because stop_times does NOT have a stop_name column.\n"
            "  * To filter trips active on a date, join gtfs.trips (t) and gtfs.calendar (c) on service_id, and check: (SELECT MAX(end_date) FROM gtfs.calendar) BETWEEN c.start_date AND c.end_date. Do NOT multiply date by interval or compare departure_time (time string) directly to end_date (date).\n"
            "  * ALWAYS write SQL aliases using plain English alphanumeric characters (e.g., 'as num_trips'). Never write Arabic words or spaces in SQL aliases, as they cause database syntax errors.\n"
            "- By default, when asked about busiest stations, lines, schedules, or statistics, ALWAYS find the latest active date in the database first (e.g., SELECT MAX(end_date) FROM gtfs.calendar) and filter all your queries to only count trips active on that specific date, rather than counting all historical database rows. State this date clearly in your response.\n"
            "- ALWAYS structure your final response to include: \n"
            "   1. **التقرير التحليلي (Analytical Report)**: Summarize the database findings (counts, bottleneck stations, throughput metrics) based on the data retrieved.\n"
            "   2. **التوصيات والنصائح (Optimization & Efficiency Recommendations)**: Provide concrete, actionable, and data-driven recommendations on how to improve public transport quality, adjust timetables, reduce transfers delay, or reallocate train trips.\n"
            "- Respond in the user's language (e.g. Arabic or English)."
        )

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Executes the tool by name and returns string output."""
        print(f"Executing tool {name} with arguments: {args}")
        try:
            if name == "search_stops":
                query = args.get("query")
                limit = args.get("limit", 5)
                results = search_stops(query, limit)
                return json.dumps(results, ensure_ascii=False)
                
            elif name == "find_route":
                start_stop_id = args.get("start_stop_id")
                end_stop_id = args.get("end_stop_id")
                departure_time = args.get("departure_time")
                results = find_routes(start_stop_id, end_stop_id, departure_time)
                return json.dumps(results, ensure_ascii=False)
                
            elif name == "run_readonly_sql":
                sql_query = args.get("sql_query", "")
                normalized = sql_query.strip().lower()
                
                # Validation checks
                if not normalized.startswith("select"):
                    return "Error: Only SELECT queries are allowed."
                
                forbidden_keywords = ["insert", "update", "delete", "drop", "truncate", "alter", "create"]
                if any(kw in normalized for kw in forbidden_keywords):
                    return f"Error: Modifying keywords are forbidden. Only read-only SELECT operations are allowed."
                
                conn = get_db_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute(sql_query)
                        rows = cur.fetchmany(50)  # limit returned rows to prevent LLM overflow
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
                return f"Error: Tool {name} not found."
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    def chat(self, user_message: str, history: List[Dict[str, Any]] = None, mode: str = "user") -> Tuple[str, List[Dict[str, Any]]]:
        """Runs the conversational agent loop with Groq. Returns (assistant_response, updated_history)."""
        if history is None:
            history = []
            
        # Select system prompt based on mode
        sys_prompt = self.analyst_system_prompt if mode == "analyst" else self.user_system_prompt
        messages = [{"role": "system", "content": sys_prompt}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
            
        messages.append({"role": "user", "content": user_message})
        
        # Add to history
        history.append({"role": "user", "content": user_message})
        
        # Agent execution loop (supports up to 10 turn iterations)
        for _ in range(10):
            if _ > 0:
                import time
                time.sleep(1.2)  # Pause to respect Groq API rate limits (TPM)
            response = self.client.chat_completion(messages, tools=self.tools)
            choice = response["choices"][0]["message"]
            print(f"\n--- Groq LLM Response (Turn {_}) ---")
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
                elif "<function" in content:
                    json_match = re.search(r"<function[^\w](\w+)(?:\))?\s*>?\s*(\{.*?\})", content, re.DOTALL)
                    if json_match:
                        func_name = json_match.group(1)
                        try:
                            func_args = json.loads(json_match.group(2))
                            text_tool_match = True
                        except Exception:
                            pass

            if tool_calls:
                # Add assistant message containing the tool calls
                messages.append(choice)
                
                # Cache to reuse outputs for identical tool calls in this turn
                tool_cache = {}
                
                # Execute each tool call
                for tc in tool_calls:
                    tc_id = tc["id"]
                    f_name = tc["function"]["name"]
                    f_args_str = tc["function"]["arguments"]
                    
                    # Create a unique key for caching based on function name and args string
                    cache_key = (f_name, f_args_str)
                    
                    if cache_key in tool_cache:
                        tool_output = tool_cache[cache_key]
                        print(f"Tool {f_name} output (CACHED): {tool_output}")
                    else:
                        try:
                            f_args = json.loads(f_args_str)
                        except Exception:
                            f_args = {}
                        tool_output = self._execute_tool(f_name, f_args)
                        print(f"Tool {f_name} output: {tool_output}")
                        tool_cache[cache_key] = tool_output
                    
                    # Append tool response
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": f_name,
                        "content": tool_output
                    })
                
                # Continue loop to send tool outputs to the model
                continue
                
            elif text_tool_match:
                # Process the text-based tool call fallback
                tool_output = self._execute_tool(func_name, func_args)
                print(f"Parsed Text-Tool {func_name} output: {tool_output}")
                
                # Append assistant choice and tool output formatted as user message to avoid schema validation errors
                messages.append(choice)
                messages.append({
                    "role": "user",
                    "content": f"[System: Output for tool '{func_name}': {tool_output}]"
                })
                
                # Continue loop
                continue
                
            else:
                # Final response generated
                final_content = content
                history.append({"role": "assistant", "content": final_content})
                return final_content, history
                
        return "I'm sorry, I encountered an issue processing your request.", history
