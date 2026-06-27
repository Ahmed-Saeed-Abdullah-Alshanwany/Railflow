from fastapi import APIRouter, HTTPException
from backend.models.agent import AgentChatRequest, AgentChatResponse, MessageModel
from backend.services.agent_service import TransitAgentService

router = APIRouter(
    prefix="/agent",
    tags=["AI Transit Agent"]
)

agent_service = TransitAgentService()

@router.post("/chat", response_model=AgentChatResponse)
def chat_with_agent(payload: AgentChatRequest):
    """
    Exposes a conversational endpoint to chat with the AI Transit Agent.
    Accepts user message and history, returns agent response text and updated history.
    """
    try:
        history_list = []
        if payload.history:
            for item in payload.history:
                history_list.append({"role": item.role, "content": item.content})
                
        response_text, updated_history = agent_service.chat(payload.message, history_list, payload.mode)
        
        # Format the dict history back into MessageModel objects
        formatted_history = [
            MessageModel(role=msg["role"], content=msg["content"])
            for msg in updated_history
        ]
        
        return AgentChatResponse(
            response=response_text,
            history=formatted_history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
