"""storage/models.py 단위 테스트."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from storage.models import (
    BrandProfile,
    BrandRules,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    MustUseName,
    Voice,
)


def test_brand_profile_minimal_required_fields():
    profile = BrandProfile(
        meta=Meta(
            brand_name="Nike KR",
            slug="nike-kr",
            analyzed_at=datetime(2026, 5, 26, 10, 0, 0),
        ),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(),
        formatting=Formatting(),
    )
    assert profile.meta.brand_name == "Nike KR"
    assert profile.brand_rules.forbidden_phrases == []
    assert profile.example_posts == []


def test_meta_requires_brand_name_and_slug():
    with pytest.raises(ValidationError):
        Meta(brand_name="Nike KR", analyzed_at=datetime.now())  # slug 누락


def test_voice_humor_level_bounds():
    with pytest.raises(ValidationError):
        Voice(humor_level=6)


def test_models_reject_unknown_fields():
    """`extra="forbid"` 회귀 가드 — spec §5 의 schema-violation 경고 흐름이 이 동작에 의존."""
    with pytest.raises(ValidationError):
        Voice(unknown_field="x")


def test_must_use_name_default_note_empty():
    name = MustUseName(term="Nike")
    assert name.note == ""


def test_brand_rules_defaults_empty_lists():
    rules = BrandRules()
    assert rules.must_use_names == []
    assert rules.forbidden_phrases == []
    assert rules.tone_guardrails == []


def test_brand_profile_roundtrip_json():
    profile = BrandProfile(
        meta=Meta(
            brand_name="Nike KR",
            slug="nike-kr",
            analyzed_at=datetime(2026, 5, 26, 10, 0, 0),
        ),
        voice=Voice(register="casual", sentence_endings=["~해요"]),
        emoji=Emoji(top=["🔥"]),
        hashtag=Hashtag(signature=["#나이키"]),
        formatting=Formatting(),
        brand_rules=BrandRules(forbidden_phrases=["최고의"]),
        example_posts=["오늘은 어제보다 1km 더. 🔥"],
    )
    dumped = profile.model_dump_json()
    restored = BrandProfile.model_validate_json(dumped)
    assert restored == profile
