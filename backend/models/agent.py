from pydantic import BaseModel
from typing import List, Optional

class MessageModel(BaseModel):
    role: str
    content: str

class AgentChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageModel]] = None
    mode: Optional[str] = "user"  # "user" or "analyst"

class AgentChatResponse(BaseModel):
    response: str
    history: List[MessageModel]
