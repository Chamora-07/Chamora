from pydantic import BaseModel
from typing import Optional

class TestScriptBase(BaseModel):
    script_name: str
    application_id: int

class TestScriptCreate(TestScriptBase):
    pass  # Used for the initial validation

class TestScriptResponse(TestScriptBase):
    id: int
    storage_path: str

    class Config:
        from_attributes = True