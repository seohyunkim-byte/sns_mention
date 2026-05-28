"""ui/register_view.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from storage.models import BrandRules, MustUseName
from ui.register_view import (
    parse_must_use_input,
    parse_rule_list_input,
    run_analysis,
)


def test_parse_rule_list_input_basic():
    text = "최고의\n1등\n\n  유일한  "
    assert parse_rule_list_input(text) == ["최고의", "1등", "유일한"]


def test_parse_rule_list_input_empty():
    assert parse_rule_list_input("") == []


def test_parse_must_use_input_with_notes():
    text = "Nike | 영문 대문자 N\n에어 조던 | 띄어쓰기 필수\n구두점없음"
    result = parse_must_use_input(text)
    assert result == [
        MustUseName(term="Nike", note="영문 대문자 N"),
        MustUseName(term="에어 조던", note="띄어쓰기 필수"),
        MustUseName(term="구두점없음", note=""),
    ]


def test_parse_must_use_input_skips_blank_lines():
    text = "Nike\n\n\n에어 조던"
    assert parse_must_use_input(text) == [
        MustUseName(term="Nike", note=""),
        MustUseName(term="에어 조던", note=""),
    ]


def test_run_analysis_builds_profile_dict():
    client = MagicMock()
    client.call_tool.return_value = {
        "voice": {"register": "casual", "address_form": "", "sentence_endings": [],
                  "avg_length_chars": 50, "humor_level": 0, "emotion_level": 0, "signature_phrases": []},
        "emoji": {"avg_per_post": 0.0, "top": [], "placement": "none"},
        "hashtag": {"avg_count": 0, "signature": [], "common": []},
        "formatting": {"line_breaks": "sparse", "uses_caps": False, "uses_bullet_markers": False},
        "topics": [],
        "example_posts": ["대표 게시물"],
    }
    rules = BrandRules(forbidden_phrases=["x"])
    posts = ["게시물 1", "게시물 2"]
    result = run_analysis(
        client=client,
        posts=posts,
        brand_name="Nike KR",
        brand_rules=rules,
    )
    assert result["voice"]["register"] == "casual"
    assert result["example_posts"] == ["대표 게시물"]
