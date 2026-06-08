from fastapi import APIRouter, HTTPException
from ..schemas.chatbot import ChatRequest, ChatResponse
from ..services.chatbot_service import generate_demo_chat_response

router = APIRouter()


@router.post("/chatbot", response_model=ChatResponse)
def chatbot_handler(request: ChatRequest):
    try:
        return generate_demo_chat_response(request.app_id, request.question)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chatbot request failed: {str(e)}")


@router.get("/chat/sessions/{session_id}")
def get_chat_session(session_id: str):
    return {"session_id": session_id, "messages": []}
