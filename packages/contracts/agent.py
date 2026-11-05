from enum import Enum
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

class AgentType(str, Enum):
    REQUIREMENT='requirement'; DISCOVERY='discovery'; MANUAL_QA='manual_qa'; AUTOMATION_ARCHITECT='automation_architect'; EXECUTION='execution'; API_QA='api_qa'; PERFORMANCE='performance'; SECURITY='security'; VISUAL_QA='visual_qa'; DEFECT='defect'; REGRESSION='regression'; REPORTING='reporting'

class AgentTaskInput(BaseModel):
    task_id: UUID
    project_id: UUID
    agent_type: AgentType
    instructions: str
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    policy_reference: str | None = None

class AgentTaskOutput(BaseModel):
    task_id: UUID
    agent_type: AgentType
    status: str
    summary: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[UUID] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
