"""Streamlit 진입점.

세션 상태:
  - `mode`: 'register' | 'generate' | None
  - `current_slug`: 선택된 브랜드 slug (generate 모드에서)
  - `register_step`: 1 | 2 | 3 (register 모드 위저드 단계)
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from storage.repo import BrandRepo
from ui.sidebar import render_sidebar

load_dotenv()

st.set_page_config(page_title="SNS Mention", page_icon="📝", layout="wide")

DATA_DIR = Path(__file__).parent / "storage" / "data" / "brands"


def _init_state() -> None:
    st.session_state.setdefault("mode", None)
    st.session_state.setdefault("current_slug", None)
    st.session_state.setdefault("register_step", 1)


def main() -> None:
    _init_state()
    repo = BrandRepo(DATA_DIR)
    render_sidebar(repo)

    mode = st.session_state.mode
    if mode == "register":
        from core.claude_client import ClaudeClient
        from ui.register_view import render_register_view
        render_register_view(repo, client_factory=ClaudeClient)
    elif mode == "generate":
        st.header(f"카피 생성 — {st.session_state.current_slug} (Task 12에서 구현)")
        st.info("Brief 입력 + 3변종 출력이 이 자리에 들어갑니다.")
    else:
        st.title("브랜드 맞춤형 인스타그램 캡션 생성기")
        st.write("왼쪽 사이드바에서 브랜드를 선택하거나 새로 등록하세요.")


if __name__ == "__main__":
    main()
