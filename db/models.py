from datetime import datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, String, Text , DateTime , func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50) , unique=True , nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True , nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255) , nullable=False)

    applications: Mapped[List["Application"]] = relationship(back_populates="user")

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
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
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    result_file_path: Mapped[Optional[str]] = mapped_column(String(512))
    
    test_script: Mapped["TestScript"] = relationship(back_populates="runs")