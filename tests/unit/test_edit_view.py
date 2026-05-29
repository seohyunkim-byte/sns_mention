"""ui/edit_view.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

import json
from datetime import datetime

import pytest

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
from ui.edit_view import _apply_edits, _format_must_use_for_edit


def _make_profile() -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name="Nike KR", slug="nike-kr", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(register="casual", signature_phrases=["Just Do It"]),
        emoji=Emoji(top=["🔥"]),
        hashtag=Hashtag(signature=["#나이키"]),
        formatting=Formatting(),
        brand_rules=BrandRules(
            must_use_names=[
                MustUseName(term="Nike", note="대문자 N"),
                MustUseName(term="에어 조던", note=""),
            ],
            forbidden_phrases=["최고의"],
            tone_guardrails=["이모지 5개 초과 금지"],
        ),
        example_posts=["오늘은 어제보다 1km 더."],
    )


def test_format_must_use_for_edit_with_and_without_notes():
    items = [
        MustUseName(term="Nike", note="대문자 N"),
        MustUseName(term="에어 조던", note=""),
    ]
    assert _format_must_use_for_edit(items) == "Nike | 대문자 N\n에어 조던"


def test_format_must_use_for_edit_empty_list():
    assert _format_must_use_for_edit([]) == ""


def test_apply_edits_updates_brand_name_and_rules():
    profile = _make_profile()
    updated = _apply_edits(
        profile=profile,
        brand_name="Nike Korea",
        must_use_text="Nike | 영문 대문자\nJust Do It | 구두점 없음",
        forbidden_text="최고의\n유일한",
        guardrails_text="정치 발언 금지",
        analyzed_json_text="",
    )
    assert updated.meta.brand_name == "Nike Korea"
    assert updated.meta.slug == "nike-kr"  # slug 는 보존
    assert [m.term for m in updated.brand_rules.must_use_names] == ["Nike", "Just Do It"]
    assert updated.brand_rules.forbidden_phrases == ["최고의", "유일한"]
    assert updated.brand_rules.tone_guardrails == ["정치 발언 금지"]
    # 분석 결과는 그대로 유지
    assert updated.voice.signature_phrases == ["Just Do It"]
    assert updated.example_posts == ["오늘은 어제보다 1km 더."]


def test_apply_edits_with_analyzed_json_updates_voice():
    profile = _make_profile()
    new_analyzed = {
        "voice": {
            "register": "polite",
            "address_form": "고객님",
            "sentence_endings": ["~합니다", "~드립니다"],
            "avg_length_chars": 150,
            "humor_level": 1,
            "emotion_level": 3,
            "signature_phrases": ["새로운 시작"],
        },
        "emoji": {"avg_per_post": 0.2, "top": ["✨"], "placement": "end_of_sentence"},
        "hashtag": {"avg_count": 5, "signature": ["#new"], "common": ["#brand"]},
        "formatting": {"line_breaks": "sparse", "uses_caps": False, "uses_bullet_markers": True},
        "topics": ["라이프스타일"],
        "example_posts": ["새로운 캡션 예시"],
    }
    updated = _apply_edits(
        profile=profile,
        brand_name="Nike KR",
        must_use_text="",
        forbidden_text="",
        guardrails_text="",
        analyzed_json_text=json.dumps(new_analyzed, ensure_ascii=False),
    )
    assert updated.voice.register == "polite"
    assert updated.voice.avg_length_chars == 150
    assert updated.emoji.top == ["✨"]
    assert updated.topics == ["라이프스타일"]


def test_apply_edits_invalid_json_raises_value_error():
    profile = _make_profile()
    with pytest.raises(ValueError, match="JSON"):
        _apply_edits(
            profile=profile,
            brand_name="Nike",
            must_use_text="",
            forbidden_text="",
            guardrails_text="",
            analyzed_json_text="{ broken json",
        )


def test_apply_edits_schema_violation_raises_value_error():
    profile = _make_profile()
    # humor_level 7 은 0~5 범위 위반
    bad_analyzed = {
        "voice": {
            "register": "casual",
            "address_form": "",
            "sentence_endings": [],
            "avg_length_chars": 0,
            "humor_level": 7,  # 위반
            "emotion_level": 0,
            "signature_phrases": [],
        }
    }
    with pytest.raises(ValueError, match="검증"):
        _apply_edits(
            profile=profile,
            brand_name="Nike",
            must_use_text="",
            forbidden_text="",
            guardrails_text="",
            analyzed_json_text=json.dumps(bad_analyzed),
        )


def test_apply_edits_strips_brand_name_whitespace():
    profile = _make_profile()
    updated = _apply_edits(
        profile=profile,
        brand_name="   Nike Korea   ",
        must_use_text="",
        forbidden_text="",
        guardrails_text="",
        analyzed_json_text="",
    )
    assert updated.meta.brand_name == "Nike Korea"


def test_apply_edits_empty_rule_inputs_clear_lists():
    profile = _make_profile()
    updated = _apply_edits(
        profile=profile,
        brand_name="Nike KR",
        must_use_text="",
        forbidden_text="",
        guardrails_text="",
        analyzed_json_text="",
    )
    assert updated.brand_rules.must_use_names == []
    assert updated.brand_rules.forbidden_phrases == []
    assert updated.brand_rules.tone_guardrails == []
