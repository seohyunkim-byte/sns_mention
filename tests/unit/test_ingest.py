"""core/ingest.py 단위 테스트 — paste/URL 파서."""
from __future__ import annotations

import pytest

from core.ingest import IngestError, extract_ig_handle, parse_pasted_posts


def test_parse_pasted_posts_basic():
    text = "첫 게시물\n둘째 줄\n---\n두번째 게시물\n---\n세번째"
    assert parse_pasted_posts(text) == [
        "첫 게시물\n둘째 줄",
        "두번째 게시물",
        "세번째",
    ]


def test_parse_pasted_posts_strips_whitespace():
    text = "   첫 게시물   \n---\n   둘째   "
    assert parse_pasted_posts(text) == ["첫 게시물", "둘째"]


def test_parse_pasted_posts_drops_empty():
    text = "첫\n---\n\n\n---\n둘"
    assert parse_pasted_posts(text) == ["첫", "둘"]


def test_parse_pasted_posts_accepts_long_divider():
    text = "첫\n-------\n둘"
    assert parse_pasted_posts(text) == ["첫", "둘"]


def test_parse_pasted_posts_empty_string_returns_empty_list():
    assert parse_pasted_posts("") == []


def test_extract_ig_handle_clean_url():
    assert extract_ig_handle("https://www.instagram.com/nike/") == "nike"


def test_extract_ig_handle_with_query_string():
    assert extract_ig_handle("https://instagram.com/nike?hl=ko") == "nike"


def test_extract_ig_handle_at_prefix():
    assert extract_ig_handle("@nike_kr") == "nike_kr"


def test_extract_ig_handle_invalid_returns_none():
    assert extract_ig_handle("not a url") is None
    assert extract_ig_handle("") is None


from unittest.mock import MagicMock, patch

from core.ingest import crawl_instagram


def _make_post(caption: str | None) -> MagicMock:
    m = MagicMock()
    m.caption = caption
    return m


@patch("core.ingest.instaloader")
def test_crawl_instagram_returns_captions(mock_il):
    profile = MagicMock()
    profile.get_posts.return_value = iter([
        _make_post("첫번째 캡션"),
        _make_post("두번째 캡션"),
    ])
    mock_il.Profile.from_username.return_value = profile
    mock_il.Instaloader.return_value = MagicMock()

    result = crawl_instagram("https://instagram.com/nike/", max_posts=10)
    assert result == ["첫번째 캡션", "두번째 캡션"]


@patch("core.ingest.instaloader")
def test_crawl_instagram_skips_empty_captions(mock_il):
    profile = MagicMock()
    profile.get_posts.return_value = iter([
        _make_post("실제 캡션"),
        _make_post(None),
        _make_post("  "),
    ])
    mock_il.Profile.from_username.return_value = profile
    mock_il.Instaloader.return_value = MagicMock()

    assert crawl_instagram("https://instagram.com/nike/", max_posts=10) == ["실제 캡션"]


@patch("core.ingest.instaloader")
def test_crawl_instagram_respects_max_posts(mock_il):
    profile = MagicMock()
    profile.get_posts.return_value = iter([
        _make_post(f"post {i}") for i in range(50)
    ])
    mock_il.Profile.from_username.return_value = profile
    mock_il.Instaloader.return_value = MagicMock()

    result = crawl_instagram("https://instagram.com/nike/", max_posts=5)
    assert len(result) == 5


@patch("core.ingest.instaloader")
def test_crawl_instagram_invalid_url_raises(mock_il):
    with pytest.raises(IngestError, match="invalid"):
        crawl_instagram("not a url")
    mock_il.Instaloader.assert_not_called()


@patch("core.ingest.instaloader")
def test_crawl_instagram_wraps_loader_errors(mock_il):
    mock_il.Profile.from_username.side_effect = Exception("login required")
    mock_il.Instaloader.return_value = MagicMock()

    with pytest.raises(IngestError, match="login required"):
        crawl_instagram("https://instagram.com/nike/")
