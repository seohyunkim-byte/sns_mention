"""브랜드 프로필 Pydantic 모델.

스펙 §2 의 JSON 스키마를 그대로 매핑한다.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MustUseName(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    note: str = ""


class BrandRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_use_names: list[MustUseName] = Field(default_factory=list)
    forbidden_phrases: list[str] = Field(default_factory=list)
    tone_guardrails: list[str] = Field(default_factory=list)


class Voice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Voice.register shadows pydantic.BaseModel.register (deprecated v1 method).
    # The warning is filtered in pytest.ini; spec §2 mandates this field name.
    register: str = "casual"
    address_form: str = ""
    sentence_endings: list[str] = Field(default_factory=list)
    avg_length_chars: int = 0
    humor_level: int = Field(default=0, ge=0, le=5)
    emotion_level: int = Field(default=0, ge=0, le=5)
    signature_phrases: list[str] = Field(default_factory=list)


class Emoji(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avg_per_post: float = 0.0
    top: list[str] = Field(default_factory=list)
    placement: str = "none"


class Hashtag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avg_count: int = 0
    signature: list[str] = Field(default_factory=list)
    common: list[str] = Field(default_factory=list)


class Formatting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_breaks: str = "sparse"
    uses_caps: bool = False
    uses_bullet_markers: bool = False


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand_name: str
    slug: str
    ig_handle: str = ""
    source_url: str = ""
    analyzed_at: datetime
    post_count: int = 0
    model_version: str = ""


class BrandProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: Meta
    voice: Voice
    emoji: Emoji
    hashtag: Hashtag
    formatting: Formatting
    topics: list[str] = Field(default_factory=list)
    brand_rules: BrandRules = Field(default_factory=BrandRules)
    example_posts: list[str] = Field(default_factory=list)
