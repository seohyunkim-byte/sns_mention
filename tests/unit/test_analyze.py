"""core/analyze.py 단위 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.analyze import ANALYZE_SCHEMA, build_analyze_prompt, extract_profile
from storage.models import BrandRules, MustUseName


def test_build_analyze_prompt_includes_brand_name_and_posts():
    system, user = build_analyze_prompt(
        posts=["게시물 1", "게시물 2"],
        brand_name="Nike KR",
        forbidden_phrases=["최고의"],
    )
    assert "톤앤매너" in system
    assert "Nike KR" in user
    assert "게시물 1" in user
    assert "게시물 2" in user
    assert "최고의" in user


def test_build_analyze_prompt_handles_empty_forbidden():
    system, user = build_analyze_prompt(posts=["x"], brand_name="B", forbidden_phrases=[])
    assert "Nike" not in user
    assert "B" in user


def test_extract_profile_calls_client_with_schema():
    client = MagicMock()
    client.call_tool.return_value = {
        "voice": {
            "register": "casual",
            "address_form": "여러분",
            "sentence_endings": ["~해요"],
            "avg_length_chars": 80,
            "humor_level": 2,
            "emotion_level": 4,
            "signature_phrases": ["Just Do It"],
        },
        "emoji": {"avg_per_post": 0.4, "top": ["🔥"], "placement": "end_of_sentence"},
        "hashtag": {"avg_count": 6, "signature": ["#나이키"], "common": ["#운동"]},
        "formatting": {"line_breaks": "frequent", "uses_caps": False, "uses_bullet_markers": False},
        "topics": ["러닝"],
        "example_posts": ["오늘은 어제보다 1km 더."],
    }

    result = extract_profile(
        client=client,
        posts=["오늘은 어제보다 1km 더."],
        brand_name="Nike KR",
        brand_rules=BrandRules(forbidden_phrases=["최고의"]),
    )

    assert result["voice"]["register"] == "casual"
    assert result["topics"] == ["러닝"]
    client.call_tool.assert_called_once()
    kwargs = client.call_tool.call_args.kwargs
    assert kwargs["tool_name"] == "emit_profile"
    assert kwargs["tool_schema"] == ANALYZE_SCHEMA


def test_extract_profile_passes_must_use_names_in_prompt():
    client = MagicMock()
    client.call_tool.return_value = {
        "voice": {"register": "casual", "address_form": "", "sentence_endings": [],
                  "avg_length_chars": 0, "humor_level": 0, "emotion_level": 0, "signature_phrases": []},
        "emoji": {"avg_per_post": 0.0, "top": [], "placement": "none"},
        "hashtag": {"avg_count": 0, "signature": [], "common": []},
        "formatting": {"line_breaks": "sparse", "uses_caps": False, "uses_bullet_markers": False},
        "topics": [],
        "example_posts": [],
    }

    rules = BrandRules(
        must_use_names=[MustUseName(term="Nike", note="대문자 N")],
        forbidden_phrases=["최고의"],
    )
    extract_profile(client=client, posts=["x"], brand_name="Nike KR", brand_rules=rules)

    user_prompt = client.call_tool.call_args.kwargs["user"]
    assert "Nike" in user_prompt
    assert "대문자 N" in user_prompt
