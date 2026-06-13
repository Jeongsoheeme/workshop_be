from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SubjectType = Literal["team", "user"]


class ResultCreate(BaseModel):
    subject_type: SubjectType
    subject_id: int


class ResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    subject_type: str
    subject_id: int
    created_at: datetime
