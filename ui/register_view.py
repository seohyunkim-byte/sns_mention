"""신규 브랜드 등록 3-step 위저드.

비-UI 헬퍼(parse_*, run_analysis)는 단위 테스트 대상.
render_*_step 함수들은 Streamlit 위젯 호출이라 통합 테스트에서만 다룸.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st
from pydantic import ValidationError

from core.analyze import extract_profile
from core.claude_client import ClaudeClient
from core.ingest import IngestError, crawl_instagram, parse_pasted_posts
from storage.models import (
    BrandProfile,
    BrandRules,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    MustUseName,
    Voice,
)
from storage.repo import BrandRepo


# --- 비-UI 헬퍼 ---------------------------------------------------------------

def parse_rule_list_input(text: str) -> list[str]:
    """한 줄에 한 항목씩. 공백 strip, 빈 줄 제거."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_must_use_input(text: str) -> list[MustUseName]:
    """'용어 | 메모' 형식, 또는 '용어' 만. 한 줄에 하나."""
    items: list[MustUseName] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "|" in line:
            term, note = line.split("|", 1)
            items.append(MustUseName(term=term.strip(), note=note.strip()))
        else:
            items.append(MustUseName(term=line, note=""))
    return items


def run_analysis(
    *,
    client: ClaudeClient,
    posts: list[str],
    brand_name: str,
    brand_rules: BrandRules,
) -> dict[str, Any]:
    return extract_profile(
        client=client, posts=posts, brand_name=brand_name, brand_rules=brand_rules,
    )


# --- Streamlit 렌더 ----------------------------------------------------------

def render_register_view(repo: BrandRepo, client_factory) -> None:
    """3-step wizard. client_factory 는 ClaudeClient 를 lazy 생성."""
    step = st.session_state.get("register_step", 1)
    st.header(f"새 브랜드 등록 — Step {step}/3")

    if step == 1:
        _render_step1_collect()
    elif step == 2:
        _render_step2_rules()
    elif step == 3:
        _render_step3_review(repo=repo, client_factory=client_factory)


def _render_step1_collect() -> None:
    st.subheader("게시물 수집")

    method = st.radio(
        "방법",
        ["IG URL 크롤 시도", "직접 붙여넣기"],
        key="step1_method",
    )

    if method == "IG URL 크롤 시도":
        url = st.text_input("Instagram URL 또는 @handle", key="step1_url")
        if st.button("크롤 시도"):
            try:
                posts = crawl_instagram(url, max_posts=30)
            except IngestError as e:
                st.error(f"크롤 실패: {e}")
                st.info("아래에서 '직접 붙여넣기'로 전환하세요.")
                return
            if not posts:
                st.warning("게시물을 가져왔지만 본문이 비어있습니다.")
                return
            st.session_state.collected_posts = posts
            st.session_state.source_url = url
            st.success(f"{len(posts)}개 게시물 수집 완료")
    else:
        st.caption("게시물 사이는 `---` 로 구분")
        raw = st.text_area("게시물들", height=300, key="step1_paste")
        if st.button("파싱"):
            posts = parse_pasted_posts(raw)
            if not posts:
                st.error("파싱된 게시물이 없습니다.")
                return
            st.session_state.collected_posts = posts
            st.session_state.source_url = ""
            st.success(f"{len(posts)}개 게시물 파싱 완료")

    posts = st.session_state.get("collected_posts", [])
    if posts:
        with st.expander(f"수집된 게시물 미리보기 ({len(posts)}개)"):
            for i, p in enumerate(posts, 1):
                st.text_area(f"#{i}", value=p, height=80, key=f"preview-{i}")
        if len(posts) < 5:
            st.warning("게시물이 5개 미만입니다. 분석 품질이 떨어질 수 있습니다.")
        if st.button("다음 →", type="primary"):
            st.session_state.register_step = 2
            st.rerun()


def _render_step2_rules() -> None:
    st.subheader("브랜드 규칙 입력")

    brand_name = st.text_input("브랜드명 (필수)", key="step2_brand_name")
    st.text_area(
        "정확 표기 명칭 (한 줄에 하나, `용어 | 메모` 형식)",
        height=120,
        key="step2_must_use",
        placeholder="Nike | 영문 대문자 N\n에어 조던 | 띄어쓰기 필수",
    )
    st.text_area(
        "금지 표현 (한 줄에 하나)",
        height=120,
        key="step2_forbidden",
        placeholder="최고의\n유일한\n1등",
    )
    st.text_area(
        "톤 가드레일 (한 줄에 하나, 선택)",
        height=80,
        key="step2_guardrails",
        placeholder="정치/종교 발언 금지\n이모지 5개 초과 금지",
    )

    col1, col2 = st.columns(2)
    if col1.button("← 이전"):
        st.session_state.register_step = 1
        st.rerun()
    if col2.button("분석 시작 →", type="primary", disabled=not brand_name):
        st.session_state.step2_data = {
            "brand_name": brand_name,
            "must_use": parse_must_use_input(st.session_state.step2_must_use),
            "forbidden": parse_rule_list_input(st.session_state.step2_forbidden),
            "guardrails": parse_rule_list_input(st.session_state.step2_guardrails),
        }
        st.session_state.register_step = 3
        st.session_state.analysis_done = False
        st.rerun()


def _render_step3_review(repo: BrandRepo, client_factory) -> None:
    st.subheader("분석 결과 검토·편집")

    data = st.session_state.get("step2_data") or {}
    posts = st.session_state.get("collected_posts") or []
    brand_rules = BrandRules(
        must_use_names=data.get("must_use", []),
        forbidden_phrases=data.get("forbidden", []),
        tone_guardrails=data.get("guardrails", []),
    )

    if not st.session_state.get("analysis_done"):
        with st.spinner("Claude 가 톤을 분석 중입니다 (10~30초)..."):
            try:
                profile_dict = run_analysis(
                    client=client_factory(),
                    posts=posts,
                    brand_name=data["brand_name"],
                    brand_rules=brand_rules,
                )
            except Exception as e:
                st.error(f"분석 실패: {e}")
                if st.button("← 이전 단계로"):
                    st.session_state.register_step = 2
                    st.rerun()
                return
            st.session_state.analyzed_profile = profile_dict
            st.session_state.analysis_done = True

    profile_dict = st.session_state.analyzed_profile

    st.json(profile_dict, expanded=False)
    st.caption("필요하면 위 JSON 을 직접 편집하지 말고, 저장 후 사이드바에서 인라인 편집하세요.")

    if st.button("저장", type="primary"):
        slug = repo.unique_slug(BrandRepo.slugify(data["brand_name"]))
        try:
            profile = BrandProfile(
                meta=Meta(
                    brand_name=data["brand_name"],
                    slug=slug,
                    source_url=st.session_state.get("source_url", ""),
                    analyzed_at=datetime.now(),
                    post_count=len(posts),
                    model_version="claude-sonnet-4-6",
                ),
                voice=Voice.model_validate(profile_dict["voice"]),
                emoji=Emoji.model_validate(profile_dict["emoji"]),
                hashtag=Hashtag.model_validate(profile_dict["hashtag"]),
                formatting=Formatting.model_validate(profile_dict["formatting"]),
                topics=profile_dict.get("topics", []),
                brand_rules=brand_rules,
                example_posts=profile_dict.get("example_posts", []),
            )
        except (KeyError, ValidationError) as e:
            st.error(f"분석 결과 스키마 위반: {e}")
            st.caption("Claude 응답이 예상 형식과 맞지 않습니다. 위 JSON 을 확인하고 '이전' 으로 돌아가 재분석하세요.")
            if st.button("← Step 2 로 돌아가기"):
                st.session_state.register_step = 2
                st.session_state.analysis_done = False
                st.rerun()
            return

        repo.save(profile)
        st.success(f"저장됨: {slug}.json")
        st.session_state.mode = "generate"
        st.session_state.current_slug = slug
        st.session_state.register_step = 1
        # cleanup
        for k in ["collected_posts", "step2_data", "analyzed_profile", "analysis_done", "source_url"]:
            st.session_state.pop(k, None)
        st.rerun()
