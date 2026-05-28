"""ui/generate_view.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
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
from storage.repo import BrandRepo
from ui.generate_view import _append_history, run_full_generation


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


def test_append_history_persists_to_repo(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    profile = _make_profile()
    repo.save(profile)

    results = [
        {"label": "감성", "caption": "오늘도 한 걸음", "hashtags": ["#nike"]},
        {"label": "정보", "caption": "6/5~6/15 사전구매", "hashtags": []},
    ]
    updated = _append_history(
        repo=repo,
        profile=profile,
        brief="6/5~6/15 사전구매 이벤트",
        results=results,
        extra_instruction="",
    )

    assert len(updated.caption_history) == 1
    entry = updated.caption_history[0]
    assert entry.brief == "6/5~6/15 사전구매 이벤트"
    assert [v.caption for v in entry.variants] == ["오늘도 한 걸음", "6/5~6/15 사전구매"]
    assert [v.label for v in entry.variants] == ["감성", "정보"]

    # 디스크에서 다시 로드해도 동일 데이터가 살아있는지 검증.
    reloaded = repo.load("nike-kr")
    assert len(reloaded.caption_history) == 1
    assert reloaded.caption_history[0].brief == "6/5~6/15 사전구매 이벤트"


def test_append_history_accumulates_multiple_generations(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    profile = _make_profile()
    repo.save(profile)

    for i in range(3):
        profile = _append_history(
            repo=repo,
            profile=profile,
            brief=f"브리프 {i}",
            results=[{"label": "감성", "caption": f"카피 {i}", "hashtags": []}],
        )

    assert len(profile.caption_history) == 3
    assert [e.brief for e in profile.caption_history] == ["브리프 0", "브리프 1", "브리프 2"]
