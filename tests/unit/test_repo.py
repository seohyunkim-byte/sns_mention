"""storage/repo.py 단위 테스트."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from storage.models import (
    BrandProfile,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    Voice,
)
from storage.repo import BrandRepo, RepoError


def _make_profile(name: str = "Nike KR", slug: str = "nike-kr") -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name=name, slug=slug, analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(),
        formatting=Formatting(),
    )


def test_slugify_basic_ascii():
    assert BrandRepo.slugify("Nike KR") == "nike-kr"


def test_slugify_korean_preserved():
    assert BrandRepo.slugify("마켓컬리") == "마켓컬리"


def test_slugify_strips_special_chars():
    assert BrandRepo.slugify("Nike @ KR!! 2026") == "nike-kr-2026"


def test_slugify_empty_string_fallback():
    assert BrandRepo.slugify("   ") == "brand"


def test_save_creates_json_file(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    profile = _make_profile()
    path = repo.save(profile)
    assert path == tmp_data_dir / "nike-kr.json"
    assert path.exists()


def test_load_returns_validated_model(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    profile = _make_profile()
    repo.save(profile)
    loaded = repo.load("nike-kr")
    assert loaded == profile


def test_load_missing_raises(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    with pytest.raises(RepoError, match="not found"):
        repo.load("missing")


def test_load_invalid_json_raises(tmp_data_dir: Path):
    (tmp_data_dir / "broken.json").write_text("{ not json", encoding="utf-8")
    repo = BrandRepo(tmp_data_dir)
    with pytest.raises(RepoError, match="invalid"):
        repo.load("broken")


def test_load_schema_violation_raises(tmp_data_dir: Path):
    (tmp_data_dir / "bad.json").write_text('{"meta": {}}', encoding="utf-8")
    repo = BrandRepo(tmp_data_dir)
    with pytest.raises(RepoError, match="schema"):
        repo.load("bad")


def test_list_returns_sorted_by_brand_name(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile("Zara", "zara"))
    repo.save(_make_profile("Adidas", "adidas"))
    repo.save(_make_profile("Nike KR", "nike-kr"))
    names = [p.meta.brand_name for p in repo.list()]
    assert names == ["Adidas", "Nike KR", "Zara"]


def test_list_skips_invalid_files_returns_warnings(tmp_data_dir: Path):
    (tmp_data_dir / "broken.json").write_text("not json", encoding="utf-8")
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile())
    profiles, warnings = repo.list_with_warnings()
    assert len(profiles) == 1
    assert any("broken" in w for w in warnings)


def test_delete_removes_file(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile())
    assert repo.delete("nike-kr") is True
    assert not (tmp_data_dir / "nike-kr.json").exists()


def test_delete_nonexistent_returns_false(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    assert repo.delete("ghost") is False


def test_unique_slug_appends_suffix_on_collision(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile("Nike", "nike"))
    assert repo.unique_slug("nike") == "nike-2"
    repo.save(_make_profile("Nike (2)", "nike-2"))
    assert repo.unique_slug("nike") == "nike-3"
