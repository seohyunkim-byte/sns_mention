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
                    st.session_state.current_slug = p.meta.slug
                    st.session_state.mode = "generate"
                    st.rerun()

        st.divider()
        if st.button("＋ 새 브랜드 등록", use_container_width=True, type="primary"):
            st.session_state.current_slug = None
            st.session_state.mode = "register"
            st.session_state.register_step = 1
            st.rerun()
