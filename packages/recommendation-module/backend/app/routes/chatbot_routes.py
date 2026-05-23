from fastapi import APIRouter, HTTPException
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.services.chatbot_service import generate_demo_chat_response

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("", response_model=ChatResponse)
def chatbot_handler(request: ChatRequest):
    try:
        return generate_demo_chat_response(request.app_id, request.question)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chatbot request failed: {str(e)}")
    

from app.services.chat_history_service import (
    get_chat_sessions,
    get_chat_messages
)
@router.get("/chat/sessions/{app_id}")
def list_chat_sessions(app_id: str):
    sessions = get_chat_sessions(app_id)

    return {
        "sessions": sessions
    }

@router.get("/chat/messages/{session_id}")
def get_session_messages(session_id: str):
    messages = get_chat_messages(session_id)

    return {
        "messages": messages
    }


