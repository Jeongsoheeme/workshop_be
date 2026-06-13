from pydantic import BaseModel, Field


class RouletteSpinRequest(BaseModel):
    options: list[str] = Field(min_length=1, description="추첨 후보 목록")
    nonce: int = Field(description="회차 식별자 (검증 재현용)")


class RouletteSpinResult(BaseModel):
    session_id: int
    nonce: int
    options: list[str]
    selected_index: int
    selected: str
    commitment: str  # sha256(seed) — 결과를 사전 약속과 연결


class CommitmentResponse(BaseModel):
    session_id: int
    commitment: str


class SeedRevealResponse(BaseModel):
    session_id: int
    seed: str
    commitment: str
