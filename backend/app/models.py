from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Minutes(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


class Meeting(BaseModel):
    id: str
    filename: str
    title: str
    created_at: datetime
    status: Literal["uploaded", "transcribed", "generated", "edited"]
    transcript: str = ""
    minutes: Minutes | None = None

