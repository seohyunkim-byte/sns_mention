"""Streamlit 진입점.

세션 상태:
  - `mode`: 'register' | 'generate' | None
  - `current_slug`: 선택된 브랜드 slug (generate 모드에서)
  - `register_step`: 1 | 2 | 3 (register 모드 위저드 단계)
  - `_authed`: 비밀번호 인증 통과 여부

비밀번호 게이트는 `APP_PASSWORD` 가 환경변수 또는 `st.secrets` 에 설정된 경우에만 활성화된다.
로컬 개발 시 패스워드 미설정이면 게이트는 비활성 — 즉시 메인 화면 진입.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from storage.repo import BrandRepo
from ui.sidebar import render_sidebar

load_dotenv()

# Streamlit Cloud 의 secrets 를 환경변수로 미러링해서 core/llm_client 가 변경 없이 동작하도록.
try:
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "APP_PASSWORD"):
        if key in st.secrets and not os.environ.get(key):
            os.environ[key] = st.secrets[key]
except Exception:
    # secrets.toml 이 없는 로컬 환경에서는 무시.
    pass

st.set_page_config(page_title="SNS Mention", page_icon="📝", layout="wide")

DATA_DIR = Path(__file__).parent / "storage" / "data" / "brands"


def _init_state() -> None:
    st.session_state.setdefault("mode", None)
    st.session_state.setdefault("current_slug", None)
    st.session_state.setdefault("register_step", 1)
    st.session_state.setdefault("_authed", False)


def _check_password() -> bool:
    """APP_PASSWORD 가 설정되어 있으면 로그인 게이트를 띄운다.

    Returns:
        True 이면 메인 앱 진입 허용, False 면 로그인 화면이 표시된 상태.
    """
    expected = os.environ.get("APP_PASSWORD", "").strip()
    if not expected:
        return True  # 로컬 개발 등 — 게이트 비활성

    if st.session_state.get("_authed"):
        return True

    st.title("🔒 SNS Mention")
    st.caption("팀 전용 도구입니다. 공유받은 비밀번호를 입력하세요.")
    pwd = st.text_input("비밀번호", type="password", key="_pwd_input")
    if st.button("입장", type="primary"):
        if pwd == expected:
            st.session_state._authed = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False


def main() -> None:
    _init_state()
    if not _check_password():
        return

    repo = BrandRepo(DATA_DIR)
    render_sidebar(repo)

    mode = st.session_state.mode
    if mode == "register":
        from core.llm_client import LLMClient
        from ui.register_view import render_register_view
        render_register_view(repo, client_factory=LLMClient)
    elif mode == "generate":
        from core.llm_client import LLMClient
        from ui.generate_view import render_generate_view
        render_generate_view(repo, client_factory=LLMClient)
    else:
        st.title("브랜드 맞춤형 인스타그램 캡션 생성기")
        st.write("왼쪽 사이드바에서 브랜드를 선택하거나 새로 등록하세요.")


if __name__ == "__main__":
    main()
