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