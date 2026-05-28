"""ui/sidebar.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from storage.models import (
    BrandProfile,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    Voice,
)
from storage.repo import BrandRepo
from ui.sidebar import load_brand_options


def test_load_brand_options_returns_sorted_with_warnings(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(
        BrandProfile(
            meta=Meta(brand_name="Zara", slug="zara", analyzed_at=datetime(2026, 5, 26)),
            voice=Voice(), emoji=Emoji(), hashtag=Hashtag(), formatting=Formatting(),
        )
    )
    repo.save(
        BrandProfile(
            meta=Meta(brand_name="Adidas", slug="adidas", analyzed_at=datetime(2026, 5, 26)),
            voice=Voice(), emoji=Emoji(), hashtag=Hashtag(), formatting=Formatting(),
        )
    )
    (tmp_data_dir / "broken.json").write_text("not json", encoding="utf-8")

    options, warnings = load_brand_options(repo)
    assert [o.meta.brand_name for o in options] == ["Adidas", "Zara"]
    assert any("broken" in w for w in warnings)


def test_load_brand_options_empty_dir(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    options, warnings = load_brand_options(repo)
    assert options == []
    assert warnings == []
