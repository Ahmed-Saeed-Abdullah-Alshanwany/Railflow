import httpx
from typing import List, Dict, Any, Optional
from backend.config import Config

class GroqClient:
    """A clean client to interact with the Groq API (OpenAI-compatible)."""
    def __init__(self):
        self.api_key = Config.GROQ_API_KEY
        self.model = Config.GROQ_MODEL
        self.api_url = f"{Config.GROQ_API_URL}/chat/completions"

    def chat_completion(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        tool_choice: str = "auto"
    ) -> Dict[str, Any]:
        """Sends a request to Groq chat completions endpoint with automatic 429 retry logic."""
        if not self.api_key or self.api_key.startswith("gsk_placeholder"):
            raise ValueError(
                "Groq API Key is not configured. Please set GROQ_API_KEY in your .env file."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2  # low temperature for stable tool calling and SQL generation
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        import time
        import re

        max_retries = 3
        default_wait = 2.0

        for attempt in range(max_retries):
            # Use httpx with a generous timeout for model processing
            with httpx.Client(timeout=45.0) as client:
                response = client.post(self.api_url, json=payload, headers=headers)
                
                if response.status_code == 429:
                    wait_time = default_wait
                    try:
                        resp_json = response.json()
                        error_message = resp_json.get("error", {}).get("message", "")
                        # Try to parse e.g. "Please try again in 1.58s."
                        match = re.search(r"try again in ([\d\.]+)s", error_message)
                        if match:
                            wait_time = float(match.group(1)) + 0.5  # add buffer
                        elif "retry-after" in response.headers:
                            wait_time = float(response.headers["retry-after"]) + 0.5
                    except Exception:
                        pass
                    
                    print(f"Rate limited (429). Waiting {wait_time:.2f}s and retrying... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue  # retry
                
                if response.status_code != 200:
                    error_msg = f"Groq API error ({response.status_code}): {response.text}"
                    print(error_msg)
                    raise Exception(error_msg)
                    
                return response.json()

        raise Exception("Failed to get response from Groq after maximum rate limit retries.")
