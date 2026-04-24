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


class AnomalyFlag(BaseModel):
    type: str
    value: float
    threshold: float
    message: str


class AnomalyData(BaseModel):
    available: bool
    status: str
    flags: List[AnomalyFlag] = []


class DashboardResponse(BaseModel):
    application: ApplicationMetadata
    metrics: MetricsData
    containers: List[ContainerInfo]
    tech_stack: TechStackData
    anomaly: AnomalyData