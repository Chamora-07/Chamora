from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class CycleStatus(str, Enum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ABORTED = "aborted"


class TestCycleStart(BaseModel):
    test_script_id: int


class TestCycleResponse(BaseModel):
    id: int
    test_script_id: int
    script_name: Optional[str] = None
    application_id: Optional[int] = None
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result_file_path: Optional[str] = None

    class Config:
        from_attributes = True
