from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RewardCreate(BaseModel):
    name: str
    description: str | None = None
    total_count: int = 1
    image_url: str | None = None


class RewardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    total_count: int | None = None
    image_url: str | None = None


class RewardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    name: str
    description: str | None
    total_count: int
    image_url: str | None
    created_at: datetime
    updated_at: datetime | None
