from pydantic import BaseModel


class ChatRequest(BaseModel):
    app_id: str
    question: str


class ChatResponse(BaseModel):
    answer: str
    mode: str