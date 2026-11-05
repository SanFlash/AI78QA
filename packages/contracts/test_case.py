from typing import Literal
from pydantic import BaseModel, Field

class TestStep(BaseModel):
    step_number: int
    action: str
    target: str | None = None
    test_data_ref: str | None = None
    expected_result: str | None = None

class TestCaseSpec(BaseModel):
    case_key: str
    title: str
    scenario: str
    priority: Literal['critical','high','medium','low']
    category: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestStep]
    assertions: list[dict] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    automation_candidate: bool = True
