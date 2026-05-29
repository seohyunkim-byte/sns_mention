"""브랜드 프로필 + Brief → 3개 카피 변종 + 한글 맞춤법 교정.

이 모듈은 `core.llm_client.LLMClient` 만 의존한다. ingest/analyze 와 상호 import 금지.
"""
from __future__ import annotations

from typing import Any

from core.llm_client import LLMClient
from storage.models import BrandProfile, BrandRules


_VARIANT_DESCRIPTIONS = {
    "종합": (
        "감정 후킹·핵심 혜택·기한/CTA 를 모두 자연스럽게 한 캡션에 녹인 추천 A 안. "
        "이걸 그대로 발행해도 손색 없도록 가장 신중하게 작성. "
        "도입부에 감정 후킹 → 중간에 혜택과 정보 → 마지막에 명확한 CTA·기한 강조 구성을 권장."
    ),
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
    client: LLMClient,
    profile: BrandProfile,
    brief: str,
    variants: list[str] | None = None,
    extra_instruction: str = "",
) -> list[dict[str, Any]]:
    """3개 변종(또는 지정된 변종) 카피를 작성해 리스트 반환."""
    variants = variants or ["종합", "감성", "정보", "이벤트 강조"]
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


PROOFREAD_SCHEMA: dict[str, Any] = GENERATE_SCHEMA  # 동일 구조


def _format_must_use_from_rules(rules: BrandRules) -> str:
    items = rules.must_use_names
    if not items:
        return "(없음)"
    return "; ".join(f"{m.term} ({m.note})" if m.note else m.term for m in items)


def proofread(
    *,
    client: LLMClient,
    captions: list[dict[str, Any]],
    brand_rules: BrandRules,
) -> list[dict[str, Any]]:
    """카피 3개를 받아 한글 맞춤법·금지어·정확표기 교정 후 동일 구조로 반환."""
    forbidden = ", ".join(brand_rules.forbidden_phrases) or "(없음)"
    must_use = _format_must_use_from_rules(brand_rules)

    system = f"""\
당신은 한국어 교정 전문가다.
아래 카피들을 검토하여 다음만 수정하라:
1. 맞춤법·띄어쓰기 오류 (국립국어원 기준)
2. 자주 틀리는 케이스: 되/돼, 안/않, 률/율, 어색한 외래어 표기
3. 금지 표현 [{forbidden}] 포함 시 자연스럽게 치환
4. 정확 표기 [{must_use}] 위반 시 교정

수정 없으면 원문 그대로 반환. 의역·재창작·톤 변경 금지. 오직 교정만.
같은 label·hashtags 를 유지하고 caption 만 손볼 것."""

    user_parts: list[str] = []
    for c in captions:
        user_parts.append(f"[{c.get('label', '')}]")
        user_parts.append(c.get("caption", ""))
        user_parts.append("---")
    user_parts.append("emit_proofread 도구로 동일 JSON 구조를 반환하라.")

    result = client.call_tool(
        system=system,
        user="\n".join(user_parts),
        tool_name="emit_proofread",
        tool_schema=PROOFREAD_SCHEMA,
    )
    return list(result.get("variants", []))
