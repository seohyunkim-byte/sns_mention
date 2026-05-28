"""인스타그램 게시물 묶음에서 브랜드 톤 프로필을 추출한다.

이 모듈은 `core.claude_client.ClaudeClient` 만 의존한다. ingest/generate 와 상호 import 금지.
"""
from __future__ import annotations

from typing import Any

from core.claude_client import ClaudeClient
from storage.models import BrandRules


ANALYZE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["voice", "emoji", "hashtag", "formatting", "topics", "example_posts"],
    "properties": {
        "voice": {
            "type": "object",
            "required": [
                "register", "address_form", "sentence_endings",
                "avg_length_chars", "humor_level", "emotion_level", "signature_phrases",
            ],
            "properties": {
                "register": {"type": "string"},
                "address_form": {"type": "string"},
                "sentence_endings": {"type": "array", "items": {"type": "string"}},
                "avg_length_chars": {"type": "integer", "minimum": 0},
                "humor_level": {"type": "integer", "minimum": 0, "maximum": 5},
                "emotion_level": {"type": "integer", "minimum": 0, "maximum": 5},
                "signature_phrases": {"type": "array", "items": {"type": "string"}},
            },
        },
        "emoji": {
            "type": "object",
            "required": ["avg_per_post", "top", "placement"],
            "properties": {
                "avg_per_post": {"type": "number", "minimum": 0},
                "top": {"type": "array", "items": {"type": "string"}},
                "placement": {"type": "string"},
            },
        },
        "hashtag": {
            "type": "object",
            "required": ["avg_count", "signature", "common"],
            "properties": {
                "avg_count": {"type": "integer", "minimum": 0},
                "signature": {"type": "array", "items": {"type": "string"}},
                "common": {"type": "array", "items": {"type": "string"}},
            },
        },
        "formatting": {
            "type": "object",
            "required": ["line_breaks", "uses_caps", "uses_bullet_markers"],
            "properties": {
                "line_breaks": {"type": "string"},
                "uses_caps": {"type": "boolean"},
                "uses_bullet_markers": {"type": "boolean"},
            },
        },
        "topics": {"type": "array", "items": {"type": "string"}},
        "example_posts": {"type": "array", "items": {"type": "string"}},
    },
}


_SYSTEM = """\
당신은 10년 차 브랜드 톤앤매너 분석 전문가다.
주어진 인스타그램 게시물들을 읽고 브랜드의 일관된 보이스를 JSON 으로 추출하라.

규칙:
- 추측 금지. 게시물에서 확인되는 패턴만 기록.
- 빈도가 낮은 표현(1~2회)은 시그니처로 보지 말 것.
- 금지어 목록과 겹치는 표현이 포함된 게시물은 example_posts 에서 제외하라.
- example_posts 는 톤이 가장 대표적인 3~5개만 발췌."""


def build_analyze_prompt(
    *,
    posts: list[str],
    brand_name: str,
    forbidden_phrases: list[str],
    must_use_names: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """(system, user) 프롬프트 페어 반환."""
    must_use_names = must_use_names or []
    lines: list[str] = [f"브랜드명: {brand_name}"]
    if forbidden_phrases:
        lines.append(f"금지 표현 (제외 대상): {', '.join(forbidden_phrases)}")
    if must_use_names:
        formatted = "; ".join(f"{term} ({note})" if note else term for term, note in must_use_names)
        lines.append(f"정확 표기 명칭: {formatted}")
    lines.append(f"게시물 ({len(posts)}개):")
    for i, post in enumerate(posts, 1):
        lines.append("---")
        lines.append(post)
    lines.append("---")
    lines.append("위 자료에서 패턴을 추출하여 emit_profile 도구로 JSON 을 반환하라.")
    return _SYSTEM, "\n".join(lines)


def extract_profile(
    *,
    client: ClaudeClient,
    posts: list[str],
    brand_name: str,
    brand_rules: BrandRules,
) -> dict[str, Any]:
    """톤 프로필을 추출해 dict 반환. 호출부에서 Meta 등을 합쳐 BrandProfile 완성."""
    system, user = build_analyze_prompt(
        posts=posts,
        brand_name=brand_name,
        forbidden_phrases=brand_rules.forbidden_phrases,
        must_use_names=[(m.term, m.note) for m in brand_rules.must_use_names],
    )
    return client.call_tool(
        system=system,
        user=user,
        tool_name="emit_profile",
        tool_schema=ANALYZE_SCHEMA,
    )
