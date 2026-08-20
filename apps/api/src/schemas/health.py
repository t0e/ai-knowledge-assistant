from datetime import datetime

from pydantic import BaseModel, Field


class ServiceComponentHealth(BaseModel):
    status: str = Field(..., examples=["healthy"])
    connected: bool = Field(..., examples=[True])
    error: str | None = None


class DatabaseHealth(ServiceComponentHealth):
    pgvector_installed: bool = Field(..., examples=[True])


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])
    project_name: str = Field(..., examples=["AI Knowledge Assistant"])
    version: str = Field(..., examples=["0.1.0"])
    environment: str = Field(..., examples=["development"])
    timestamp: datetime
    database: DatabaseHealth
    redis: ServiceComponentHealth


class ProbeResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    timestamp: datetime
