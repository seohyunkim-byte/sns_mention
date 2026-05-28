"""core/ingest.py 단위 테스트 — paste/URL 파서."""
from __future__ import annotations

import pytest

from core.ingest import extract_ig_handle, parse_pasted_posts


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
