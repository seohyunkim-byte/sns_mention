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

    header_col, edit_col, delete_col = st.columns([6, 1, 1])
    header_col.header(profile.meta.brand_name)
    if edit_col.button("✏️ 수정", key="edit_brand_btn", use_container_width=True):
        st.session_state.mode = "edit"
        st.rerun()
    if delete_col.button("🗑 삭제", key="delete_brand_btn", use_container_width=True):
        st.session_state.confirm_delete_slug = slug

    st.caption(
        f"register: {profile.voice.register} · 평균 길이: {profile.voice.avg_length_chars}자 · "
        f"이모지 평균: {profile.emoji.avg_per_post:.1f}/post"
    )

    # 삭제 확인 UI — confirm_delete_slug 가 현재 브랜드와 일치할 때만 표시
    if st.session_state.get("confirm_delete_slug") == slug:
        history_count = len(profile.caption_history)
        st.warning(
            f"⚠️ **'{profile.meta.brand_name}'** 브랜드와 생성 히스토리 {history_count}개가 "
            f"영구 삭제됩니다. 이 작업은 되돌릴 수 없습니다."
        )
        cancel_col, confirm_col = st.columns(2)
        if cancel_col.button("취소", key="cancel_delete_btn", use_container_width=True):
            st.session_state.pop("confirm_delete_slug", None)
            st.rerun()
        if confirm_col.button(
            "정말 삭제", type="primary", key="really_delete_btn", use_container_width=True
        ):
            repo.delete(slug)
            # 잔존 상태 정리
            for k in (
                "confirm_delete_slug",
                "current_slug",
                "last_results",
                "last_brief",
                "brief_input",
            ):
                st.session_state.pop(k, None)
            st.session_state.mode = None
            st.rerun()
        return  # 확인 중일 때는 나머지 화면 숨김

    with st.expander("브랜드 프로필 / 규칙 보기", expanded=False):
        st.json(profile.model_dump(), expanded=False)
        st.caption("프로필 항목을 수정하려면 상단의 ✏️ 수정 버튼을 누르세요.")

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
            caption_text = variant.get("caption", "")
            # 위젯 key 에 caption 텍스트 해시를 포함 — 카피가 바뀌면 자동으로 다른 위젯이
            # 생성되어 streamlit text_area 의 session_state 캐시가 stale 값을 보여주는
            # 문제를 완전히 차단한다. gen_id 와 함께 belt-and-suspenders.
            caption_key = f"caption-{gen_id}-{i}-{abs(hash(caption_text)) & 0xFFFFFFFF:08x}"
            st.markdown(f"**변종 {i + 1} [{label}]**")
            st.text_area(
                "caption",
                value=caption_text,
                height=120,
                key=caption_key,
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
