from pydantic import BaseModel, Field
from typing import List

class ExecutionPlan(BaseModel):
    intent: str = Field(..., description="The core intent of the user's request, e.g., chat, research, vision, task")
    execution_plan: List[str] = Field(..., description="An array of clean text instructions for multi-step execution")
