"""카피 생성 화면.

비-UI 헬퍼(run_full_generation)는 generate.write_captions + generate.proofread 를 합쳐
한 번에 3-변종 생성 + 맞춤법 교정을 수행한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from core.generate import proofread, write_captions
from core.llm_client import LLMClient
from storage.models import (
    BrandProfile,
    CaptionGeneration,
    CaptionVariant,
)
from storage.repo import BrandRepo


# --- 비-UI 헬퍼 ---------------------------------------------------------------

def run_full_generation(
    *,
    client: LLMClient,
    profile: BrandProfile,
    brief: str,
    variants: list[str] | None = None,
    extra_instruction: str = "",
) -> list[dict[str, Any]]:
    """1차: 카피 생성 → 2차: 한글 맞춤법·금지어 교정. 교정된 리스트를 반환."""
    generated = write_captions(
        client=client, profile=profile, brief=brief,
        variants=variants, extra_instruction=extra_instruction,
    )
    if not generated:
        return []
    return proofread(client=client, captions=generated, brand_rules=profile.brand_rules)


def _append_history(
    *,
    repo: BrandRepo,
    profile: BrandProfile,
    brief: str,
    results: list[dict[str, Any]],
    extra_instruction: str = "",
) -> BrandProfile:
    """방금 생성된 카피를 BrandProfile.caption_history 에 누적 저장."""
    entry = CaptionGeneration(
        generated_at=datetime.now(),
        brief=brief,
        variants=[CaptionVariant.model_validate(v) for v in results],
        extra_instruction=extra_instruction,
        model_version=LLMClient.DEFAULT_MODEL,
    )
    profile.caption_history.append(entry)
    repo.save(profile)
    return profile


# --- Streamlit 렌더 ----------------------------------------------------------

def render_generate_view(repo: BrandRepo, client_factory) -> None:
    slug = st.session_state.get("current_slug")
    if not slug:
        st.info("사이드바에서 브랜드를 선택하세요.")
        return

    try:
        profile = repo.load(slug)
    except Exception as e:
        st.error(f"브랜드 로드 실패: {e}")
        return

    st.header(profile.meta.brand_name)
    st.caption(
        f"register: {profile.voice.register} · 평균 길이: {profile.voice.avg_length_chars}자 · "
        f"이모지 평균: {profile.emoji.avg_per_post:.1f}/post"
    )

    with st.expander("브랜드 프로필 / 규칙 보기·편집", expanded=False):
        st.json(profile.model_dump(), expanded=False)
        st.caption("MVP: 인라인 편집은 v2 에서 지원. 지금은 JSON 파일 직접 편집 후 새로고침.")

    brief = st.text_area(
        "Brief (이벤트·신상품 등 핵심 정보)",
        height=140,
        key="brief_input",
        placeholder="6/5~6/15 사전 구매 시 도시락 가방+물병 증정. 한정 수량 200세트.",
    )

    col1, col2, col3 = st.columns(3)
    use_emotional = col1.checkbox("감성", value=True)
    use_factual = col2.checkbox("정보", value=True)
    use_event = col3.checkbox("이벤트 강조", value=True)

    selected: list[str] = []
    if use_emotional:
        selected.append("감성")
    if use_factual:
        selected.append("정보")
    if use_event:
        selected.append("이벤트 강조")

    if st.button("🚀 카피 생성", type="primary", disabled=not (brief.strip() and selected)):
        with st.spinner("AI 가 카피를 작성하고 맞춤법을 검증합니다..."):
            try:
                results = run_full_generation(
                    client=client_factory(),
                    profile=profile,
                    brief=brief,
                    variants=selected,
                )
            except Exception as e:
                st.error(f"생성 실패: {e}")
                return
        # 위젯 key 네임스페이스를 새로 발급해서 이전 카피가 text_area session_state 에
        # 박혀있던 문제를 해결한다 (text_area 는 key 가 있으면 session_state 값을 우선시함).
        st.session_state.gen_id = st.session_state.get("gen_id", 0) + 1
        st.session_state.last_results = results
        st.session_state.last_brief = brief
        profile = _append_history(repo=repo, profile=profile, brief=brief, results=results)
        st.success("✓ 맞춤법 검증 완료")

    results = st.session_state.get("last_results") or []
    gen_id = st.session_state.get("gen_id", 0)
    for i, variant in enumerate(results):
        with st.container(border=True):
            label = variant.get("label", "")
            st.markdown(f"**변종 {i + 1} [{label}]**")
            st.text_area(
                "caption",
                value=variant.get("caption", ""),
                height=120,
                key=f"caption-{gen_id}-{i}",
                label_visibility="collapsed",
            )
            tags = " ".join(variant.get("hashtags", []))
            st.caption(tags or "(해시태그 없음)")

            with st.expander("🔄 이 변종만 다시 생성"):
                extra = st.text_input(
                    "추가 지시 (예: 더 짧게 / 감정 톤 더 살려)",
                    key=f"extra-{gen_id}-{i}",
                )
                if st.button("재생성", key=f"regen-{gen_id}-{i}"):
                    with st.spinner("재생성 중..."):
                        try:
                            new_variants = run_full_generation(
                                client=client_factory(),
                                profile=profile,
                                brief=st.session_state.get("last_brief", brief),
                                variants=[label],
                                extra_instruction=extra,
                            )
                        except Exception as e:
                            st.error(f"재생성 실패: {e}")
                            new_variants = []
                    if new_variants:
                        results[i] = new_variants[0]
                        st.session_state.gen_id = gen_id + 1
                        st.session_state.last_results = results
                        _append_history(
                            repo=repo,
                            profile=profile,
                            brief=st.session_state.get("last_brief", brief),
                            results=new_variants,
                            extra_instruction=extra,
                        )
                        st.rerun()

    # 카피 히스토리 (생성한 모든 카피를 시간 역순으로 보관)
    if profile.caption_history:
        st.divider()
        with st.expander(f"📜 생성 히스토리 ({len(profile.caption_history)}개)", expanded=False):
            for idx, entry in enumerate(reversed(profile.caption_history)):
                ts = entry.generated_at.strftime("%Y-%m-%d %H:%M")
                brief_preview = entry.brief if len(entry.brief) <= 100 else entry.brief[:100] + "..."
                header = f"#{len(profile.caption_history) - idx} · {ts}"
                if entry.extra_instruction:
                    header += f" · 재생성 (추가 지시: {entry.extra_instruction})"
                st.markdown(f"**{header}**")
                st.caption(f"Brief: {brief_preview}")
                for v in entry.variants:
                    st.markdown(f"- **[{v.label}]** {v.caption}")
                    if v.hashtags:
                        st.caption("  " + " ".join(v.hashtags))
                if idx < len(profile.caption_history) - 1:
                    st.markdown("---")
