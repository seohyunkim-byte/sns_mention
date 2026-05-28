"""core/generate.py 단위 테스트 — 카피 작성."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from core.generate import (
    GENERATE_SCHEMA,
    PROOFREAD_SCHEMA,
    build_generate_prompt,
    proofread,
    write_captions,
)
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


def _make_profile() -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name="Nike KR", slug="nike-kr", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(register="casual", signature_phrases=["Just Do It"], sentence_endings=["~해요"]),
        emoji=Emoji(top=["🔥"], avg_per_post=0.4),
        hashtag=Hashtag(signature=["#나이키"], common=["#운동"]),
        formatting=Formatting(),
        brand_rules=BrandRules(
            must_use_names=[MustUseName(term="Nike", note="대문자 N")],
            forbidden_phrases=["최고의", "아디다스"],
            tone_guardrails=["이모지 5개 초과 금지"],
        ),
        example_posts=["오늘은 어제보다 1km 더. 🔥"],
    )


def test_build_generate_prompt_contains_all_sections():
    profile = _make_profile()
    system, user = build_generate_prompt(profile=profile, brief="6/5~6/15 사전구매 이벤트", variants=["감성", "정보", "이벤트 강조"])

    assert "Nike KR" in system
    assert "최고의" in system
    assert "아디다스" in system
    assert "Nike" in system and "대문자 N" in system
    assert "국립국어원" in system
    assert "감성" in system and "정보" in system and "이벤트 강조" in system

    assert "Just Do It" in user
    assert "오늘은 어제보다 1km" in user
    assert "이모지 5개 초과 금지" in user
    assert "6/5~6/15 사전구매 이벤트" in user


def test_build_generate_prompt_filters_variants():
    profile = _make_profile()
    system, _ = build_generate_prompt(profile=profile, brief="x", variants=["감성"])
    assert "감성" in system
    assert "정보" not in system
    assert "이벤트 강조" not in system


def test_build_generate_prompt_includes_extra_instruction():
    profile = _make_profile()
    _, user = build_generate_prompt(
        profile=profile, brief="x", variants=["감성"], extra_instruction="더 짧게, 한 문장으로",
    )
    assert "더 짧게, 한 문장으로" in user


def test_write_captions_returns_variants_list():
    client = MagicMock()
    client.call_tool.return_value = {
        "variants": [
            {"label": "감성", "caption": "오늘도 한 걸음. 🔥", "hashtags": ["#나이키", "#러닝"]},
            {"label": "정보", "caption": "6/5~6/15 사전구매 시 도시락 가방 증정.", "hashtags": ["#이벤트"]},
            {"label": "이벤트 강조", "caption": "단 10일! Just Do It.", "hashtags": ["#한정"]},
        ]
    }

    profile = _make_profile()
    result = write_captions(client=client, profile=profile, brief="6/5~6/15 사전구매 이벤트")

    assert len(result) == 3
    assert result[0]["label"] == "감성"
    client.call_tool.assert_called_once()
    kwargs = client.call_tool.call_args.kwargs
    assert kwargs["tool_name"] == "emit_variants"
    assert kwargs["tool_schema"] == GENERATE_SCHEMA


def test_write_captions_passes_extra_instruction():
    client = MagicMock()
    client.call_tool.return_value = {"variants": []}
    profile = _make_profile()
    write_captions(
        client=client,
        profile=profile,
        brief="x",
        variants=["감성"],
        extra_instruction="더 부드럽게",
    )
    assert "더 부드럽게" in client.call_tool.call_args.kwargs["user"]


def test_proofread_returns_corrected_variants():
    client = MagicMock()
    client.call_tool.return_value = {
        "variants": [
            {"label": "감성", "caption": "오늘도 한 걸음 더. 🔥", "hashtags": ["#나이키"]},
        ]
    }

    rules = BrandRules(forbidden_phrases=["최고의"])
    captions = [{"label": "감성", "caption": "오늘도 한 걸음더 🔥", "hashtags": ["#나이키"]}]

    result = proofread(client=client, captions=captions, brand_rules=rules)
    assert result[0]["caption"] == "오늘도 한 걸음 더. 🔥"

    kwargs = client.call_tool.call_args.kwargs
    assert kwargs["tool_name"] == "emit_proofread"
    assert kwargs["tool_schema"] == PROOFREAD_SCHEMA
    assert "최고의" in kwargs["system"]
    assert "맞춤법" in kwargs["system"]


def test_proofread_passes_original_captions_in_user_prompt():
    client = MagicMock()
    client.call_tool.return_value = {"variants": []}
    captions = [
        {"label": "감성", "caption": "원문 1", "hashtags": []},
        {"label": "정보", "caption": "원문 2", "hashtags": []},
    ]
    proofread(client=client, captions=captions, brand_rules=BrandRules())
    user_prompt = client.call_tool.call_args.kwargs["user"]
    assert "원문 1" in user_prompt
    assert "원문 2" in user_prompt
