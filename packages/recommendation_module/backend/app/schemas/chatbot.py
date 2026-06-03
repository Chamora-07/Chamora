from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    app_id: str
    question: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    mode: str
    session_id: Optional[str] = None
    sources: List[str] = []


class ChatSessionSummary(BaseModel):
    id: str
    application_id: str
    title: str
    preview: str
    timestamp: Optional[str] = None
    mode: str
    status: str


class ChatMessageItem(BaseModel):
    id: str
    type: str
    content: str
    details: Optional[str] = None
    timestamp: Optional[str] = None