from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TestScriptBase(BaseModel):
    script_name: str
    application_id: int


class TestScriptResponse(TestScriptBase):
    id: int
    storage_path: str

    class Config:
        from_attributes = True


class TestRunResponse(BaseModel):
    id: int
    test_script_id: int
    status: str           # queued | running | completed | failed
    start_time: datetime
    end_time: Optional[datetime] = None
    result_file_path: Optional[str] = None

    class Config:
        from_attributes = True