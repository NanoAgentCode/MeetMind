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


ProviderProtocol = Literal["openai", "anthropic", "ollama", "openai_compatible"]
ModelType = Literal["llm", "rag", "asr"]


class ProviderInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    protocol: ProviderProtocol
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(default="", max_length=1000)
    enabled: bool = True


class Provider(BaseModel):
    id: str
    name: str
    protocol: ProviderProtocol
    base_url: str
    enabled: bool
    api_key_configured: bool = False
    api_key_masked: str = ""
    created_at: datetime


class ModelConfigInput(BaseModel):
    provider_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    model_type: ModelType
    enabled: bool = True
    is_default: bool = False


class ModelConfig(BaseModel):
    id: str
    provider_id: str
    name: str
    model_id: str
    model_type: ModelType
    enabled: bool
    is_default: bool
    created_at: datetime


class MeetingQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class MeetingAnswer(BaseModel):
    answer: str
