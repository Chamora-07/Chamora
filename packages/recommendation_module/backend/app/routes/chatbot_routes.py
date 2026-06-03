from fastapi import APIRouter, HTTPException
from ..schemas.chatbot import ChatRequest, ChatResponse, ChatSessionSummary, ChatMessageItem
from ..services.chatbot_service import generate_demo_chat_response
from ..services.chat_history_service import get_chat_sessions, get_chat_messages

router = APIRouter()


@router.post("/chatbot", response_model=ChatResponse)
def chatbot_handler(request: ChatRequest):
    try:
        return generate_demo_chat_response(request.app_id, request.question, request.session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chatbot request failed: {str(e)}")


@router.get("/chat/sessions/{app_id}")
def chat_sessions(app_id: str) -> dict[str, list[ChatSessionSummary]]:
    try:
        return {"sessions": get_chat_sessions(app_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load chat sessions: {str(e)}")


@router.get("/chat/messages/{session_id}")
def chat_messages(session_id: str) -> dict[str, list[ChatMessageItem]]:
    try:
        return {"messages": get_chat_messages(session_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load chat messages: {str(e)}")