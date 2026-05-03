from pydantic import BaseModel, ConfigDict

class HealthCheckResponse(BaseModel):
    status: str
    version: str

class ErrorResponse(BaseModel):
    error: str
    details: str | None = None
