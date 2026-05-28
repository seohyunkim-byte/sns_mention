"""사이드바 — 브랜드 목록 + 신규 등록 버튼.

순수 로직(`load_brand_options`)은 별도 함수로 빼서 단위 테스트 가능.
Streamlit 렌더링(`render_sidebar`)은 호출부에서 사용.
"""
from __future__ import annotations

import streamlit as st

from storage.models import BrandProfile
from storage.repo import BrandRepo


def load_brand_options(repo: BrandRepo) -> tuple[list[BrandProfile], list[str]]:
    """저장된 브랜드 프로필 목록과 로드 경고를 반환."""
    return repo.list_with_warnings()


_GENERATE_STATE_KEYS = ("last_results", "last_brief", "brief_input")


def _clear_generate_state() -> None:
    """브랜드 전환 시 이전 브랜드의 캡션/브리프 잔존 상태 제거."""
    for k in _GENERATE_STATE_KEYS:
        st.session_state.pop(k, None)


def render_sidebar(repo: BrandRepo) -> None:
    """사이드바 렌더. 세션 상태 키: `current_slug`, `mode` ('register' | 'generate')."""
    with st.sidebar:
        st.title("📚 브랜드")
        profiles, warnings = load_brand_options(repo)

        for w in warnings:
            st.warning(f"⚠️ {w}")

        if not profiles:
            st.caption("등록된 브랜드가 없습니다.")
        else:
            for p in profiles:
                if st.button(p.meta.brand_name, key=f"brand-{p.meta.slug}", use_container_width=True):
                    if st.session_state.get("current_slug") != p.meta.slug:
                        _clear_generate_state()
                    st.session_state.current_slug = p.meta.slug
                    st.session_state.mode = "generate"
                    st.rerun()

        st.divider()
        if st.button("＋ 새 브랜드 등록", use_container_width=True, type="primary"):
            _clear_generate_state()
            st.session_state.current_slug = None
            st.session_state.mode = "register"
            st.session_state.register_step = 1
            st.rerun()
