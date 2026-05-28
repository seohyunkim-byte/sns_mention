"""인스타그램 게시물 수집.

두 가지 수집 경로:
  1. parse_pasted_posts: 마케터가 ---로 구분해 붙여넣은 텍스트
  2. crawl_instagram:    instaloader 베스트-에포트 크롤 (Task 6)
"""
from __future__ import annotations

import re
from urllib.parse import urlparse


class IngestError(Exception):
    """수집 실패."""


_DIVIDER_RE = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]+$")


def parse_pasted_posts(text: str) -> list[str]:
    """`---` (3 hyphens+) 라인으로 텍스트 블록 분리. 공백 strip 후 빈 블록 제거."""
    if not text:
        return []
    chunks = _DIVIDER_RE.split(text)
    return [c.strip() for c in chunks if c.strip()]


def extract_ig_handle(value: str) -> str | None:
    """IG URL 또는 @handle 에서 핸들만 추출. 못 뽑으면 None."""
    if not value:
        return None
    s = value.strip()
    if s.startswith("@"):
        candidate = s[1:]
        return candidate if _HANDLE_RE.match(candidate) else None
    try:
        parsed = urlparse(s if "://" in s else f"https://{s}")
    except ValueError:
        return None
    if "instagram.com" not in (parsed.netloc or ""):
        return None
    path = (parsed.path or "").strip("/")
    if not path:
        return None
    candidate = path.split("/", 1)[0]
    return candidate if _HANDLE_RE.match(candidate) else None
