from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

class WebsiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    base_url: HttpUrl
    environment_type: str = Field(default="demo", pattern="^(demo|staging|local)$")

class WebsiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    base_url: str
    environment_type: str
    created_at: datetime

class SessionCreate(BaseModel):
    website_id: str
    max_pages: int = Field(default=30, ge=1, le=100)
    max_depth: int = Field(default=3, ge=0, le=5)
    mode: str = Field(default="observe", pattern="^observe$")

class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    website_id: str
    status: str
    max_pages: int
    max_depth: int
    summary: dict
    created_at: datetime

class HealthRead(BaseModel):
    status: str
    service: str
    version: str
