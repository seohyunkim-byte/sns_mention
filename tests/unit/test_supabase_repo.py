"""storage/supabase_repo.py 단위 테스트.

실제 Supabase 호출 없이 SDK 의 chain 패턴(table().select().eq().execute())을 MagicMock 으로
재현해서 메서드 동작을 검증한다.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from storage.models import (
    BrandProfile,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    Voice,
)
from storage.repo import RepoError
from storage.supabase_repo import SupabaseBrandRepo


def _make_profile(name: str = "Nike KR", slug: str = "nike-kr") -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name=name, slug=slug, analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(),
        formatting=Formatting(),
    )


def _client_with_result(data: list[dict]) -> MagicMock:
    """Supabase SDK chain 의 최종 execute() 결과를 고정값으로 반환하는 mock."""
    client = MagicMock()
    response = MagicMock()
    response.data = data
    # chain 모든 단계가 self 같은 객체를 반환 — execute() 만 응답 객체.
    table = client.table.return_value
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.upsert.return_value = table
    table.delete.return_value = table
    table.execute.return_value = response
    return client


def test_exists_true_when_row_present():
    client = _client_with_result([{"slug": "nike-kr"}])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    assert repo.exists("nike-kr") is True


def test_exists_false_when_empty():
    client = _client_with_result([])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    assert repo.exists("ghost") is False


def test_load_returns_validated_profile():
    profile = _make_profile()
    client = _client_with_result([{"data": profile.model_dump(mode="json")}])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    loaded = repo.load("nike-kr")
    assert loaded.meta.brand_name == "Nike KR"


def test_load_missing_raises():
    client = _client_with_result([])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    with pytest.raises(RepoError, match="not found"):
        repo.load("missing")


def test_load_schema_violation_raises():
    client = _client_with_result([{"data": {"meta": {}}}])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    with pytest.raises(RepoError, match="schema"):
        repo.load("bad")


def test_save_upserts_with_jsonb_payload():
    client = _client_with_result([])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    profile = _make_profile()
    result = repo.save(profile)
    assert result == "nike-kr"
    # upsert 가 정확한 페이로드로 호출됐는지 검증
    upsert_call = client.table.return_value.upsert.call_args
    payload = upsert_call.args[0]
    assert payload["slug"] == "nike-kr"
    assert payload["data"]["meta"]["brand_name"] == "Nike KR"


def test_list_with_warnings_collects_validation_failures():
    profile = _make_profile()
    client = _client_with_result([
        {"slug": "nike-kr", "data": profile.model_dump(mode="json")},
        {"slug": "broken", "data": {"meta": {}}},
    ])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    profiles, warnings = repo.list_with_warnings()
    assert len(profiles) == 1
    assert profiles[0].meta.brand_name == "Nike KR"
    assert any("broken" in w for w in warnings)


def test_list_returns_sorted_by_brand_name():
    client = _client_with_result([
        {"slug": "z", "data": _make_profile("Zara", "z").model_dump(mode="json")},
        {"slug": "a", "data": _make_profile("Adidas", "a").model_dump(mode="json")},
        {"slug": "n", "data": _make_profile("Nike KR", "n").model_dump(mode="json")},
    ])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    names = [p.meta.brand_name for p in repo.list()]
    assert names == ["Adidas", "Nike KR", "Zara"]


def test_delete_returns_false_when_missing():
    client = _client_with_result([])  # exists() returns False
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    assert repo.delete("ghost") is False
    # delete 자체는 호출되지 않아야 함
    client.table.return_value.delete.assert_not_called()


def test_delete_returns_true_after_removal():
    # exists() 가 True 를 한 번 반환하도록 stub
    client = MagicMock()
    table = client.table.return_value
    response = MagicMock()
    response.data = [{"slug": "nike-kr"}]
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.delete.return_value = table
    table.execute.return_value = response

    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    assert repo.delete("nike-kr") is True
    table.delete.assert_called_once()


def test_slugify_delegates_to_brand_repo():
    """slugify 는 BrandRepo 와 동일 알고리즘 — 검증."""
    assert SupabaseBrandRepo.slugify("Nike KR") == "nike-kr"
    assert SupabaseBrandRepo.slugify("마켓컬리") == "마켓컬리"


def test_unique_slug_no_collision():
    client = _client_with_result([])
    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    assert repo.unique_slug("nike") == "nike"


def test_unique_slug_appends_suffix_on_collision():
    """exists 가 True 한 번 → False 한 번 패턴으로 'nike-2' 가 첫 무충돌."""
    client = MagicMock()
    table = client.table.return_value
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table

    # exists 가 호출될 때마다 execute() 가 새 response 반환 — side_effect 사용
    responses = [
        MagicMock(data=[{"slug": "nike"}]),     # nike 있음
        MagicMock(data=[]),                      # nike-2 없음
    ]
    table.execute.side_effect = responses

    repo = SupabaseBrandRepo(url="x", key="y", client=client)
    assert repo.unique_slug("nike") == "nike-2"
