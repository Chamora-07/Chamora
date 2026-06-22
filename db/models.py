import uuid
from datetime import datetime
from typing import List, Optional , Dict , Any
from sqlalchemy import ForeignKey, String, Text , DateTime , func , Float , Boolean , Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from db.base import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50) , unique=True , nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True , nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255) , nullable=False)

    applications: Mapped[List["Application"]] = relationship(back_populates="owner")

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    github_repo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    grafana_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    victoria_metrics_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    health_endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    owner: Mapped["User"] = relationship(back_populates="applications")
    endpoints: Mapped[List["Endpoint"]] = relationship(back_populates="application", cascade="all, delete")
    documents: Mapped[List["Document"]] = relationship(back_populates="application")
    test_scripts: Mapped[List["TestScript"]] = relationship(back_populates="application")

class Endpoint(Base):
    __tablename__ = "endpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    target_name: Mapped[str] = mapped_column(String(255))
    container_name: Mapped[str] = mapped_column(String(255)) 
    
    application: Mapped["Application"] = relationship(back_populates="endpoints")

    anomaly_config: Mapped[Optional["AnomalyDetectionConfig"]] = relationship(
        back_populates="endpoint", 
        uselist=False, # One model per endpoint combination
        cascade="all, delete"
    )

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    file_name: Mapped[str] = mapped_column(String(255))
    
    storage_path: Mapped[str] = mapped_column(String(512))
    
    application: Mapped["Application"] = relationship(back_populates="documents")

class TestScript(Base):
    __tablename__ = "test_scripts"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    script_name: Mapped[str] = mapped_column(String(255))

    storage_path: Mapped[str] = mapped_column(String(512))
    
    application: Mapped["Application"] = relationship(back_populates="test_scripts")
    runs: Mapped[List["TestRun"]] = relationship(back_populates="test_script")

class TestRun(Base):
    __tablename__ = "test_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_script_id: Mapped[int] = mapped_column(ForeignKey("test_scripts.id"))
    status: Mapped[str] = mapped_column(String(50))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    result_file_path: Mapped[Optional[str]] = mapped_column(String(512))
    
    test_script: Mapped["TestScript"] = relationship(back_populates="runs")

class AnomalyDetectionConfig(Base):
    """
    This table stores the 'Personalized' thresholds for a specific 
    probe + container combination.
    """
    __tablename__ = "anomaly_detection_configs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("endpoints.id", ondelete="CASCADE"), unique=True)
    
    # User-defined threshold values
    latency_threshold: Mapped[float] = mapped_column(Float, default=1.5)
    error_rate_threshold: Mapped[float] = mapped_column(Float, default=0.05)
    failure_streak_limit: Mapped[int] = mapped_column(Integer, default=3)
    cpu_usage_threshold: Mapped[float] = mapped_column(Float, default=0.8)
    memory_pressure_threshold: Mapped[float] = mapped_column(Float, default=0.9)
    disk_io_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    cpu_node_ratio_threshold: Mapped[float] = mapped_column(Float, default=0.5)
    
    # Controls if the retriever should be actively scraping this model
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Meta data
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    endpoint: Mapped["Endpoint"] = relationship(back_populates="anomaly_config")

    ml_inference_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ml_inference_need : Mapped[bool] = mapped_column(Boolean, default=False)

class Anomaly(Base):
    """
    Stores historical records of detected anomalies (WARNING and CRITICAL)
    derived from the 3-point sliding window analysis.
    """
    __tablename__ = "anomalies"

    # Using UUID for high-frequency logging to avoid ID exhaustion
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), 
        index=True
    )
    
    config_id: Mapped[int] = mapped_column(
        ForeignKey("anomaly_detection_configs.id", ondelete="CASCADE")
    )

    # Timing & Scoring details from the center of the window (T2)
    window_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False) # 'WARNING' or 'CRITICAL'
    root_cause: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Evidence snapshot of the 12 window-averaged features
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    # Relationships
    application: Mapped["Application"] = relationship()
    config: Mapped["AnomalyDetectionConfig"] = relationship()

class MLModelMetric(Base):
    """Stores the historical 'IQ' scores of the ML model for user visibility."""
    __tablename__ = "ml_model_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.gen_random_uuid()
    )
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("anomaly_detection_configs.id", ondelete="CASCADE"), index=True)
    
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    recall_score: Mapped[float] = mapped_column(Float, nullable=False)
    precision_score: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy_score: Mapped[float] = mapped_column(Float, default=0.0)
    f1_score: Mapped[float] = mapped_column(Float, default=0.0)
    evaluation_type: Mapped[str] = mapped_column(String(20), nullable=False) # 'rule_based' or 'synthetic'
    is_promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())