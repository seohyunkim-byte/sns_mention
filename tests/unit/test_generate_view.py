"""ui/generate_view.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from storage.models import (
    BrandProfile,
    BrandRules,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    Voice,
)
from ui.generate_view import run_full_generation


def _make_profile() -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name="Nike KR", slug="nike-kr", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(),
        formatting=Formatting(),
        brand_rules=BrandRules(forbidden_phrases=["최고의"]),
        example_posts=["예시"],
    )


def test_run_full_generation_calls_generate_then_proofread():
    client = MagicMock()
    client.call_tool.side_effect = [
        {"variants": [
            {"label": "감성", "caption": "원본1", "hashtags": ["#a"]},
            {"label": "정보", "caption": "원본2", "hashtags": ["#b"]},
            {"label": "이벤트 강조", "caption": "원본3", "hashtags": ["#c"]},
        ]},
        {"variants": [
            {"label": "감성", "caption": "교정1", "hashtags": ["#a"]},
            {"label": "정보", "caption": "교정2", "hashtags": ["#b"]},
            {"label": "이벤트 강조", "caption": "교정3", "hashtags": ["#c"]},
        ]},
    ]

    result = run_full_generation(
        client=client,
        profile=_make_profile(),
        brief="6/5~6/15 이벤트",
    )

    assert [v["caption"] for v in result] == ["교정1", "교정2", "교정3"]
    assert client.call_tool.call_count == 2
    assert client.call_tool.call_args_list[0].kwargs["tool_name"] == "emit_variants"
    assert client.call_tool.call_args_list[1].kwargs["tool_name"] == "emit_proofread"


def test_run_full_generation_with_variant_filter_skips_proofread_for_empty():
    client = MagicMock()
    client.call_tool.return_value = {"variants": []}
    result = run_full_generation(
        client=client,
        profile=_make_profile(),
        brief="x",
        variants=["감성"],
    )
    assert result == []
