from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    app_id: str
    question: str
    # session_id removed for stateless chatbot


class ChatResponse(BaseModel):
    answer: str
    mode: str
    sources: List[str] = []
