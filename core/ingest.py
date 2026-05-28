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


import instaloader  # noqa: E402  (Task 6 추가)


def crawl_instagram(url_or_handle: str, max_posts: int = 30) -> list[str]:
    """베스트-에포트 IG 캡션 크롤. 실패 시 IngestError 발생.

    인스타그램 정책상 자주 깨진다. 호출부는 반드시 try/except 로 받고
    paste fallback UI 로 전환해야 한다.
    """
    handle = extract_ig_handle(url_or_handle)
    if not handle:
        raise IngestError(f"invalid IG URL or handle: {url_or_handle!r}")

    try:
        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
        )
        profile = instaloader.Profile.from_username(loader.context, handle)
        captions: list[str] = []
        for post in profile.get_posts():
            if len(captions) >= max_posts:
                break
            caption = (post.caption or "").strip()
            if caption:
                captions.append(caption)
        return captions
    except IngestError:
        raise
    except Exception as e:  # instaloader 의 모든 예외를 단일 타입으로 압축
        raise IngestError(str(e)) from e
