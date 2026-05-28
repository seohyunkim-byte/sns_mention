"""브랜드 프로필 + Brief → 3개 카피 변종 + 한글 맞춤법 교정.

이 모듈은 `core.claude_client.ClaudeClient` 만 의존한다. ingest/analyze 와 상호 import 금지.
"""
from __future__ import annotations

from typing import Any

from core.claude_client import ClaudeClient
from storage.models import BrandProfile


_VARIANT_DESCRIPTIONS = {
    "감성": "감정·스토리·공감 중심",
    "정보": "혜택·스펙·이유 중심",
    "이벤트 강조": "한정성·CTA·기간 강조",
}


GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["variants"],
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "caption", "hashtags"],
                "properties": {
                    "label": {"type": "string"},
                    "caption": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def _format_must_use(profile: BrandProfile) -> str:
    rules = profile.brand_rules.must_use_names
    if not rules:
        return "(없음)"
    return "; ".join(f"{m.term} ({m.note})" if m.note else m.term for m in rules)


def _format_variant_block(variants: list[str]) -> str:
    lines = []
    for i, label in enumerate(variants, 1):
        desc = _VARIANT_DESCRIPTIONS.get(label, label)
        lines.append(f"   - 변종 {i} ({label}): {desc}")
    return "\n".join(lines)


def build_generate_prompt(
    *,
    profile: BrandProfile,
    brief: str,
    variants: list[str],
    extra_instruction: str = "",
) -> tuple[str, str]:
    """(system, user) 프롬프트 페어 반환."""
    forbidden = ", ".join(profile.brand_rules.forbidden_phrases) or "(없음)"
    must_use = _format_must_use(profile)
    variant_block = _format_variant_block(variants)

    system = f"""\
당신은 {profile.meta.brand_name} 의 인스타그램 카피라이터다.
아래 브랜드 프로필을 완벽히 학습하여, Brief 를 카피 변종으로 작성하라.

[중요 제약 — 위반 시 실격]
1. 다음 표현은 절대 사용 금지: {forbidden}
2. 다음 명칭은 정확히 이 표기로만: {must_use}
3. 국립국어원 표준 맞춤법·띄어쓰기 엄격 준수.
4. Brief 에 없는 사실(가격·기간·수량) 임의 생성 금지.
5. 변종별 차별점:
{variant_block}

emit_variants 도구로 JSON 을 반환하라."""

    voice = profile.voice
    emoji = profile.emoji
    hashtag = profile.hashtag
    formatting = profile.formatting

    user_parts: list[str] = []
    user_parts.append("=== 브랜드 프로필 ===")
    user_parts.append(
        f"- register: {voice.register}\n"
        f"- address_form: {voice.address_form}\n"
        f"- sentence_endings: {voice.sentence_endings}\n"
        f"- avg_length_chars: {voice.avg_length_chars}\n"
        f"- humor_level: {voice.humor_level}\n"
        f"- emotion_level: {voice.emotion_level}\n"
        f"- emoji top: {emoji.top}, avg_per_post: {emoji.avg_per_post}, placement: {emoji.placement}\n"
        f"- hashtag signature: {hashtag.signature}\n"
        f"- hashtag common: {hashtag.common}\n"
        f"- avg hashtag count: {hashtag.avg_count}\n"
        f"- formatting: line_breaks={formatting.line_breaks}, "
        f"uses_caps={formatting.uses_caps}, uses_bullet_markers={formatting.uses_bullet_markers}"
    )
    user_parts.append("\n=== 시그니처 표현 (자연스럽게 1~2개 활용) ===")
    user_parts.append(", ".join(voice.signature_phrases) or "(없음)")

    user_parts.append("\n=== 대표 게시물 (이 톤으로 써라) ===")
    for ex in profile.example_posts:
        user_parts.append("---")
        user_parts.append(ex)

    user_parts.append("\n=== 톤 가드레일 ===")
    user_parts.append("\n".join(f"- {g}" for g in profile.brand_rules.tone_guardrails) or "(없음)")

    user_parts.append("\n=== Brief ===")
    user_parts.append(brief)

    if extra_instruction:
        user_parts.append("\n=== 추가 지시 (이 변종만) ===")
        user_parts.append(extra_instruction)

    user_parts.append(f"\n=== 작성할 변종 ({len(variants)}개) ===")
    user_parts.append(", ".join(variants))

    return system, "\n".join(user_parts)


def write_captions(
    *,
    client: ClaudeClient,
    profile: BrandProfile,
    brief: str,
    variants: list[str] | None = None,
    extra_instruction: str = "",
) -> list[dict[str, Any]]:
    """3개 변종(또는 지정된 변종) 카피를 작성해 리스트 반환."""
    variants = variants or ["감성", "정보", "이벤트 강조"]
    system, user = build_generate_prompt(
        profile=profile, brief=brief, variants=variants, extra_instruction=extra_instruction,
    )
    result = client.call_tool(
        system=system,
        user=user,
        tool_name="emit_variants",
        tool_schema=GENERATE_SCHEMA,
    )
    return list(result.get("variants", []))
