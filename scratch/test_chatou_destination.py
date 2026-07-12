import sys, os
sys.path.insert(0, ".")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv; load_dotenv()
from backend.services.agent_service import TransitAgentService

agent = TransitAgentService()
response, _ = agent.chat("ما هي محطة الوصول للرحلات التي تمر بـ Chatou - Croissy؟", [], mode="user")
print("\n=== Agent Response ===")
print(response)
