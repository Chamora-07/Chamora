from typing import List, Optional
from pydantic import BaseModel


class ApplicationMetadata(BaseModel):
    app_id: str
    app_name: str
    domain: str
    environment: str
    user_id: str
    user_name: str
    repo_url: str
    description: Optional[str] = ""


class MetricsData(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used: str
    memory_total: str
    source: str


class ContainerInfo(BaseModel):
    name: str
    image: str
    status: str
    labels: dict = {}
    environment: dict = {}


class TechStackData(BaseModel):
    frontend: str
    backend: str
    database: str
    apis: List[str] = []
    evidence: List[str] = []


class AnomalyData(BaseModel):
    id: Optional[str] = None
    application_id: Optional[str] = None
    anomaly_detected: bool = False
    mode: str = "advisory"
    severity: Optional[str] = None
    summary: Optional[str] = None
    window_timestamp: Optional[str] = None
    score: Optional[float] = None
    root_cause: Optional[str] = None
    evidence: List[str] = []
    created_at: Optional[str] = None


class DashboardResponse(BaseModel):
    application: ApplicationMetadata
    metrics: MetricsData
    containers: List[ContainerInfo]
    tech_stack: TechStackData
    anomaly: AnomalyData