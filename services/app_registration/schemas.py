from pydantic import BaseModel , ConfigDict
from typing import List, Optional

class EndpointCreate(BaseModel):
    target_name: str
    container_name: str

class EndpointResponse(BaseModel):
    id: int
    application_id: int
    target_name: str
    container_name: str

    model_config = ConfigDict(from_attributes=True)

class ApplicationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    github_repo: Optional[str] = None
    grafana_url: Optional[str] = None
    victoria_metrics_url: Optional[str] = None
    endpoints: List[EndpointCreate] = []

class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    github_repo: Optional[str]
    endpoints: List[EndpointResponse] = []
    
    model_config = ConfigDict(from_attributes=True)