"""브랜드 등록 정보 수정 화면.

등록 시 입력했던 항목(브랜드명, 정확 표기, 금지 표현, 톤 가드레일)을 사후에 수정한다.
분석 결과(voice/emoji/hashtag/formatting/topics/example_posts)는 별도 JSON 편집 영역에서.

이 모듈은 register_view 의 파서 헬퍼(`parse_must_use_input`, `parse_rule_list_input`)를 재사용한다.
"""
from __future__ import annotations

import streamlit as st

from storage.models import BrandProfile, MustUseName
from storage.repo import BrandRepo
from ui.register_view import parse_must_use_input, parse_rule_list_input


def _format_must_use_for_edit(items: list[MustUseName]) -> str:
    """저장된 MustUseName 리스트를 등록 폼과 동일한 'term | note' 텍스트로 직렬화."""
    return "\n".join(
        f"{m.term} | {m.note}" if m.note else m.term for m in items
    )


def render_edit_view(repo: BrandRepo) -> None:
    slug = st.session_state.get("current_slug")
    if not slug:
        st.error("브랜드가 선택되지 않았습니다. 사이드바에서 브랜드를 먼저 고르세요.")
        return

    try:
        profile = repo.load(slug)
    except Exception as e:
        st.error(f"브랜드 로드 실패: {e}")
        return

    st.header(f"✏️ 브랜드 수정 — {profile.meta.brand_name}")
    st.caption(f"슬러그(변경 불가): `{profile.meta.slug}`")

    brand_name = st.text_input(
        "브랜드명 (필수)",
        value=profile.meta.brand_name,
        key="edit_brand_name",
    )

    must_use_input = st.text_area(
        "정확 표기 명칭 (한 줄에 하나, `용어 | 메모` 형식)",
        value=_format_must_use_for_edit(profile.brand_rules.must_use_names),
        height=120,
        key="edit_must_use",
        placeholder="Nike | 영문 대문자 N\n에어 조던 | 띄어쓰기 필수",
    )

    forbidden_input = st.text_area(
        "금지 표현 (한 줄에 하나)",
        value="\n".join(profile.brand_rules.forbidden_phrases),
        height=120,
        key="edit_forbidden",
        placeholder="최고의\n유일한\n1등",
    )

    guardrails_input = st.text_area(
        "톤 가드레일 (한 줄에 하나, 선택)",
        value="\n".join(profile.brand_rules.tone_guardrails),
        height=80,
        key="edit_guardrails",
        placeholder="정치/종교 발언 금지\n이모지 5개 초과 금지",
    )

    with st.expander("고급: 분석 결과 직접 편집 (JSON)", expanded=False):
        st.caption(
            "voice / emoji / hashtag / formatting / topics / example_posts 를 JSON 으로 편집합니다. "
            "Pydantic 검증을 통과해야 저장됩니다."
        )
        analyzed_subset = {
            "voice": profile.voice.model_dump(),
            "emoji": profile.emoji.model_dump(),
            "hashtag": profile.hashtag.model_dump(),
            "formatting": profile.formatting.model_dump(),
            "topics": profile.topics,
            "example_posts": profile.example_posts,
        }
        import json as _json

        st.text_area(
            "분석 결과 JSON",
            value=_json.dumps(analyzed_subset, ensure_ascii=False, indent=2),
            height=400,
            key="edit_analyzed_json",
        )

    col1, col2 = st.columns(2)
    if col1.button("← 취소"):
        st.session_state.mode = "generate"
        st.rerun()

    if col2.button("저장", type="primary", disabled=not brand_name.strip()):
        try:
            updated = _apply_edits(
                profile=profile,
                brand_name=brand_name,
                must_use_text=must_use_input,
                forbidden_text=forbidden_input,
                guardrails_text=guardrails_input,
                analyzed_json_text=st.session_state.get("edit_analyzed_json", ""),
            )
        except ValueError as e:
            st.error(f"저장 실패: {e}")
            return

        repo.save(updated)
        st.success(f"'{updated.meta.brand_name}' 저장됨")
        st.session_state.mode = "generate"
        st.rerun()


def _apply_edits(
    *,
    profile: BrandProfile,
    brand_name: str,
    must_use_text: str,
    forbidden_text: str,
    guardrails_text: str,
    analyzed_json_text: str,
) -> BrandProfile:
    """폼 입력값으로 BrandProfile 의 사본을 만들어 반환. 검증 실패 시 ValueError."""
    import json as _json

    data = profile.model_dump()
    data["meta"]["brand_name"] = brand_name.strip()
    data["brand_rules"]["must_use_names"] = [
        m.model_dump() for m in parse_must_use_input(must_use_text)
    ]
    data["brand_rules"]["forbidden_phrases"] = parse_rule_list_input(forbidden_text)
    data["brand_rules"]["tone_guardrails"] = parse_rule_list_input(guardrails_text)

    if analyzed_json_text.strip():
        try:
            parsed = _json.loads(analyzed_json_text)
        except _json.JSONDecodeError as e:
            raise ValueError(f"JSON 파싱 실패: {e}") from e
        for key in ("voice", "emoji", "hashtag", "formatting", "topics", "example_posts"):
            if key in parsed:
                data[key] = parsed[key]

    try:
        return BrandProfile.model_validate(data)
    except Exception as e:
        raise ValueError(f"스키마 검증 실패: {e}") from e
