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
                    "hashtags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 10,
                    },
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


_VARIANT_STRUCTURE_HINTS = {
    "종합": "종합 (A안 추천): [감정 후킹 1줄] → [핵심 혜택·정보 2~3줄] → [기한·CTA 1줄] + 해시태그",
    "감성": "감성: 일상 장면·감각 묘사로 시작 → 브랜드와의 정서적 연결 → 부드러운 안내",
    "정보": "정보: 혜택 명확히 → 구체 스펙·이유 → 행동 유도",
    "이벤트 강조": "이벤트 강조: 한정성·기간을 첫 문장에 → 조건 명시 → 강한 CTA",
}


def _format_structure_hints(variants: list[str]) -> str:
    """선택된 변종에 대해서만 권장 구조 가이드를 만든다 — 다른 변종 이름이 시스템 프롬프트에 새지 않게."""
    hints = [
        f"- {_VARIANT_STRUCTURE_HINTS[v]}"
        for v in variants
        if v in _VARIANT_STRUCTURE_HINTS
    ]
    return "\n".join(hints) if hints else "(권장 구조 없음 — 변종 설명을 따르세요)"


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
    structure_hints = _format_structure_hints(variants)

    system = f"""\
당신은 10년 차 한국 인스타그램 마케팅 카피라이터다.
{profile.meta.brand_name} 의 톤을 완벽히 흡수해, 마케터가 검수 없이 그대로 발행할 수 있는
최종안 수준의 카피를 작성한다.

[작성 원칙]
1. 첫 문장은 스크롤을 멈추게 하는 후킹. 평범한 정보 나열·인사말로 시작 X.
   예시 좋은 후킹: 의외의 질문 / 강한 감각적 표현 / 작은 일상 장면 한 컷.
2. Brief 의 핵심 요소(혜택·기간·수량·조건)는 100% 정확히 옮긴다. 누락도 첨가도 X.
3. 한 문장은 18~30자, **전체 캡션은 250~450자**가 기본. 인스타 '더 보기'를 펼치게
   만들 만큼 충실하게 작성. 너무 짧으면 정보가 빈약하고, 너무 길면 가독성이 떨어진다.
   ("더 짧게/더 길게" 같은 추가 지시가 있을 때만 이 범위를 벗어나도 된다.)
4. 줄바꿈은 브랜드 프로필의 line_breaks 설정을 따른다.
5. 이모지는 emoji.avg_per_post 수치에 맞춰 자연스럽게. 강제 X.
6. 브랜드 시그니처 표현이 있으면 1~2회 자연스럽게 녹인다. 억지 삽입 X.
7. **해시태그는 변종마다 반드시 10개 이상**. 우선순위:
   (1) 브랜드 시그니처 해시태그 — 무조건 포함
   (2) 브랜드 자주 쓰는(common) 해시태그에서 Brief 와 관련된 것
   (3) Brief 의 핵심 키워드(제품·이벤트·기간)에서 도출한 신규 해시태그
   중복·동어반복 금지. 너무 길거나 어색한 한국어 조합 금지.

[절대 금지 — 위반 시 실격]
1. 광고법 위반 단정 표현: '최고', '최고의', '유일한', '1등', '단언컨대', '확실히 ~', '반드시 ~',
   '완벽한', '가장 ~한' (객관적 근거 없는 단정).
2. 사용 금지 표현: {forbidden}
3. 정확 표기 강제 (대소문자·띄어쓰기 포함): {must_use}
4. Brief 에 없는 사실(가격·기간·수량·혜택·장소) 임의 생성 X.
5. 영어 단어 남발 (꼭 필요한 브랜드명·고유명사·일반화된 외래어만).
6. 불릿(•, -, ※)·번호 매기기·헤딩 사용 X — 인스타 본문에 안 어울림.
7. 형식적·딱딱한 보도자료·공문 어투 X.

[국문 품질]
- 국립국어원 표준 맞춤법·띄어쓰기 엄격 준수.
- 외래어는 표준 표기로 (예: Adobe→어도비, Microsoft→마이크로소프트).
- 자주 틀리는 부분: 되/돼, 안/않, 률/율, '수 있다' / '한 번' / '할 만한' 띄어쓰기.

[변종별 차별점]
{variant_block}

[변종별 권장 구조 — 가이드라인]
{structure_hints}

emit_variants 도구로 JSON 반환. caption 은 줄바꿈·이모지를 포함한 발행안 원문 그대로."""

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


MIN_HASHTAGS = 10


def _ensure_min_hashtags(
    variant: dict[str, Any],
    profile: BrandProfile,
    minimum: int = MIN_HASHTAGS,
) -> dict[str, Any]:
    """변종의 해시태그가 `minimum` 미만이면 브랜드 프로필의 signature/common 에서 보충.

    LLM 이 minItems=10 스키마를 항상 지키지는 못하기 때문에 코드 레벨에서 강제한다.
    중복은 케이스-인센서티브로 제거하고, 시그니처가 우선.
    """
    existing = [h for h in (variant.get("hashtags") or []) if isinstance(h, str) and h.strip()]
    seen = {h.lower() for h in existing}

    if len(existing) >= minimum:
        return variant

    pool: list[str] = list(profile.hashtag.signature) + list(profile.hashtag.common)
    for tag in pool:
        if len(existing) >= minimum:
            break
        if not tag or not isinstance(tag, str):
            continue
        normalized = tag.strip()
        if not normalized:
            continue
        if normalized.lower() in seen:
            continue
        existing.append(normalized)
        seen.add(normalized.lower())

    # 그래도 부족하면 브랜드명 기반 일반 해시태그로 채워서 최소 갯수 보장.
    fallback_pool = [
        f"#{profile.meta.brand_name}",
        "#일상", "#추천", "#이벤트", "#소식", "#신상",
        "#데일리", "#좋아요", "#팔로우", "#인스타그램", "#감성", "#라이프",
    ]
    for tag in fallback_pool:
        if len(existing) >= minimum:
            break
        if tag.lower() not in seen:
            existing.append(tag)
            seen.add(tag.lower())

    variant = dict(variant)  # 입력 사본 보호
    variant["hashtags"] = existing
    return variant


def write_captions(
    *,
    client: LLMClient,
    profile: BrandProfile,
    brief: str,
    variants: list[str] | None = None,
    extra_instruction: str = "",
) -> list[dict[str, Any]]:
    """3개 변종(또는 지정된 변종) 카피를 작성해 리스트 반환.

    LLM 이 hashtag minItems 를 위반해도 _ensure_min_hashtags 가 브랜드 프로필에서
    보충해 항상 10개 이상이 보장된다.
    """
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
    raw_variants = list(result.get("variants", []))
    return [_ensure_min_hashtags(v, profile) for v in raw_variants]


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
당신은 한국 인스타그램 발행물 최종 교정 전문가다. 발행 직전에 오류만 깔끔히 정리한다.

[교정 범위]
1. 국립국어원 표준 맞춤법·띄어쓰기 모든 오류.
2. 자주 틀리는 케이스 — 반드시 점검:
   - 되/돼: '되어'로 풀어 자연스러우면 '돼'. 예: 안돼요 → 안 돼요, 됬다 → 됐다.
   - 안/않: '아니'로 풀어 자연스러우면 '않'. 예: 안된다 / 않는다.
   - 률/율: 받침 있는 한자+률(합격률), 받침 없는 한자+율(비율).
   - 띄어쓰기: '수 있다', '할 수', '한 번', '한 명', '~할 만한', '~할 수밖에', '한 가지'.
   - 외래어 표준 표기: Adobe→어도비, Microsoft→마이크로소프트, Apple→애플,
     Coffee→커피, contents→콘텐츠, message→메시지.
3. 금지 표현 [{forbidden}] 포함 시 자연스럽게 치환.
4. 정확 표기 [{must_use}] 위반 시 교정 (대소문자·띄어쓰기 포함).
5. 광고법 위반 단정 표현 — '최고', '유일한', '1등', '단언컨대', '확실히 ~', '반드시 ~',
   '완벽한' — 자연스러운 완곡 표현으로 치환 ('손꼽히는', '돋보이는', '대표', '꼭 한번' 등).

[엄수 — 절대 위반 X]
- 수정 필요 없으면 원문 그대로 반환.
- 의역·재창작·톤 변경·길이 변경 금지. 오직 오류·금지어·정확표기 교정만.
- label, hashtags 는 절대 변경하지 말 것. caption 의 줄바꿈·이모지 위치 가능한 보존."""

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
