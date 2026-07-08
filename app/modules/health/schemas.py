from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy"]
    service: str
    version: str
    timestamp: datetime


class DependencyHealthResponse(BaseModel):
    status: Literal["healthy"]
    provider: str
    latency_ms: int

