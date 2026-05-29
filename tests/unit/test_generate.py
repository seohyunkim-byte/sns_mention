"""core/generate.py 단위 테스트 — 카피 작성."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from core.generate import (
    GENERATE_SCHEMA,
    MIN_HASHTAGS,
    PROOFREAD_SCHEMA,
    _ensure_min_hashtags,
    build_generate_prompt,
    proofread,
    write_captions,
)
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


def _make_profile() -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name="Nike KR", slug="nike-kr", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(register="casual", signature_phrases=["Just Do It"], sentence_endings=["~해요"]),
        emoji=Emoji(top=["🔥"], avg_per_post=0.4),
        hashtag=Hashtag(signature=["#나이키"], common=["#운동"]),
        formatting=Formatting(),
        brand_rules=BrandRules(
            must_use_names=[MustUseName(term="Nike", note="대문자 N")],
            forbidden_phrases=["최고의", "아디다스"],
            tone_guardrails=["이모지 5개 초과 금지"],
        ),
        example_posts=["오늘은 어제보다 1km 더. 🔥"],
    )


def test_build_generate_prompt_contains_all_sections():
    profile = _make_profile()
    system, user = build_generate_prompt(profile=profile, brief="6/5~6/15 사전구매 이벤트", variants=["감성", "정보", "이벤트 강조"])

    assert "Nike KR" in system
    assert "최고의" in system
    assert "아디다스" in system
    assert "Nike" in system and "대문자 N" in system
    assert "국립국어원" in system
    assert "감성" in system and "정보" in system and "이벤트 강조" in system

    assert "Just Do It" in user
    assert "오늘은 어제보다 1km" in user
    assert "이모지 5개 초과 금지" in user
    assert "6/5~6/15 사전구매 이벤트" in user


def test_build_generate_prompt_filters_variants():
    """선택되지 않은 변종 라벨이 variant_block 이나 structure_hints 에 새지 않아야 한다.

    참고: '정보' 같은 단어는 일반 한국어 어휘로도 등장하므로(예: '핵심 요소'),
    변종 누출 검증은 변종 라벨 패턴('(정보)', '(이벤트 강조):') 으로 정확하게 확인한다.
    """
    profile = _make_profile()
    system, _ = build_generate_prompt(profile=profile, brief="x", variants=["감성"])
    # 선택된 변종은 변종 블록·권장 구조 양쪽 모두에 포함되어야 함.
    assert "(감성)" in system
    assert "감성: 일상 장면" in system
    # 선택되지 않은 변종 라벨은 어디에도 없어야 함.
    assert "(정보)" not in system
    assert "(이벤트 강조)" not in system
    assert "정보:" not in system
    assert "이벤트 강조:" not in system


def test_build_generate_prompt_includes_extra_instruction():
    profile = _make_profile()
    _, user = build_generate_prompt(
        profile=profile, brief="x", variants=["감성"], extra_instruction="더 짧게, 한 문장으로",
    )
    assert "더 짧게, 한 문장으로" in user


def test_write_captions_returns_variants_list():
    client = MagicMock()
    client.call_tool.return_value = {
        "variants": [
            {"label": "감성", "caption": "오늘도 한 걸음. 🔥", "hashtags": ["#나이키", "#러닝"]},
            {"label": "정보", "caption": "6/5~6/15 사전구매 시 도시락 가방 증정.", "hashtags": ["#이벤트"]},
            {"label": "이벤트 강조", "caption": "단 10일! Just Do It.", "hashtags": ["#한정"]},
        ]
    }

    profile = _make_profile()
    result = write_captions(client=client, profile=profile, brief="6/5~6/15 사전구매 이벤트")

    assert len(result) == 3
    assert result[0]["label"] == "감성"
    client.call_tool.assert_called_once()
    kwargs = client.call_tool.call_args.kwargs
    assert kwargs["tool_name"] == "emit_variants"
    assert kwargs["tool_schema"] == GENERATE_SCHEMA


def test_write_captions_default_variants_include_comprehensive_first():
    """기본 변종 리스트가 ['종합', '감성', '정보', '이벤트 강조'] 4개이고 '종합'이 맨 앞이어야 한다."""
    client = MagicMock()
    client.call_tool.return_value = {"variants": []}
    profile = _make_profile()
    write_captions(client=client, profile=profile, brief="x")  # variants 미지정 → 기본 사용
    system = client.call_tool.call_args.kwargs["system"]
    # system 프롬프트의 변종 블록에 모든 4개가 포함되고 종합이 변종 1번이어야 함.
    assert "변종 1 (종합)" in system
    assert "감성" in system
    assert "정보" in system
    assert "이벤트 강조" in system
    # 종합의 설명 키워드가 prompt 에 들어가야 함.
    assert "감정 후킹" in system or "한 캡션에 모두 녹인" in system


def test_write_captions_passes_extra_instruction():
    client = MagicMock()
    client.call_tool.return_value = {"variants": []}
    profile = _make_profile()
    write_captions(
        client=client,
        profile=profile,
        brief="x",
        variants=["감성"],
        extra_instruction="더 부드럽게",
    )
    assert "더 부드럽게" in client.call_tool.call_args.kwargs["user"]


def test_ensure_min_hashtags_backfills_from_signature_and_common():
    profile = BrandProfile(
        meta=Meta(brand_name="Brand", slug="brand", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(
            signature=["#sig1", "#sig2", "#sig3"],
            common=["#com1", "#com2", "#com3", "#com4", "#com5", "#com6", "#com7"],
        ),
        formatting=Formatting(),
    )
    variant = {"label": "감성", "caption": "x", "hashtags": ["#existing1", "#existing2"]}
    result = _ensure_min_hashtags(variant, profile)
    assert len(result["hashtags"]) >= MIN_HASHTAGS
    # 기존 태그는 우선 보존되고, signature → common 순서로 보충
    assert result["hashtags"][0] == "#existing1"
    assert result["hashtags"][1] == "#existing2"
    assert "#sig1" in result["hashtags"]
    assert "#com1" in result["hashtags"]


def test_ensure_min_hashtags_no_change_when_already_enough():
    profile = BrandProfile(
        meta=Meta(brand_name="Brand", slug="brand", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(), emoji=Emoji(),
        hashtag=Hashtag(signature=["#sig"], common=["#com"]),
        formatting=Formatting(),
    )
    tags = [f"#tag{i}" for i in range(12)]
    variant = {"label": "감성", "caption": "x", "hashtags": list(tags)}
    result = _ensure_min_hashtags(variant, profile)
    assert result["hashtags"] == tags  # 변경 없음
    assert "#sig" not in result["hashtags"]  # 이미 충분하므로 시그니처 안 추가


def test_ensure_min_hashtags_falls_back_to_brand_name_pool_when_profile_thin():
    """프로필 해시태그가 적어도 최소 갯수는 채워야 한다."""
    profile = BrandProfile(
        meta=Meta(brand_name="MyBrand", slug="mb", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(), emoji=Emoji(),
        hashtag=Hashtag(signature=[], common=[]),
        formatting=Formatting(),
    )
    variant = {"label": "감성", "caption": "x", "hashtags": []}
    result = _ensure_min_hashtags(variant, profile)
    assert len(result["hashtags"]) >= MIN_HASHTAGS


def test_ensure_min_hashtags_skips_duplicates_case_insensitive():
    profile = BrandProfile(
        meta=Meta(brand_name="Brand", slug="brand", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(), emoji=Emoji(),
        hashtag=Hashtag(signature=["#Nike"], common=["#nike"]),  # 대소문자만 다른 중복
        formatting=Formatting(),
    )
    variant = {"label": "감성", "caption": "x", "hashtags": ["#nike"]}
    result = _ensure_min_hashtags(variant, profile)
    # 같은 태그 (대소문자만 다름) 가 두 번 들어가지 않아야 함
    lowered = [h.lower() for h in result["hashtags"]]
    assert len(lowered) == len(set(lowered))


def test_write_captions_backfills_hashtags_on_thin_model_output():
    """모델이 해시태그를 적게 줘도 write_captions 가 자동 보충."""
    client = MagicMock()
    client.call_tool.return_value = {
        "variants": [
            {"label": "종합", "caption": "x", "hashtags": ["#a", "#b"]},  # 2개만
        ]
    }
    profile = _make_profile()  # signature=["#나이키"], common=["#운동"]
    result = write_captions(client=client, profile=profile, brief="x")
    assert len(result[0]["hashtags"]) >= MIN_HASHTAGS
    assert "#a" in result[0]["hashtags"]
    assert "#b" in result[0]["hashtags"]


def test_generate_schema_hashtags_has_min_items_10():
    """LLM 측에서도 minItems=10 으로 강제하는지 스키마 점검."""
    hashtag_schema = GENERATE_SCHEMA["properties"]["variants"]["items"]["properties"]["hashtags"]
    assert hashtag_schema.get("minItems") == 10


def test_build_generate_prompt_requires_10_hashtags_and_length_guidance():
    profile = _make_profile()
    system, _ = build_generate_prompt(profile=profile, brief="x", variants=["감성"])
    assert "10개 이상" in system
    assert "250~450자" in system or "250-450자" in system


def test_proofread_returns_corrected_variants():
    client = MagicMock()
    client.call_tool.return_value = {
        "variants": [
            {"label": "감성", "caption": "오늘도 한 걸음 더. 🔥", "hashtags": ["#나이키"]},
        ]
    }

    rules = BrandRules(forbidden_phrases=["최고의"])
    captions = [{"label": "감성", "caption": "오늘도 한 걸음더 🔥", "hashtags": ["#나이키"]}]

    result = proofread(client=client, captions=captions, brand_rules=rules)
    assert result[0]["caption"] == "오늘도 한 걸음 더. 🔥"

    kwargs = client.call_tool.call_args.kwargs
    assert kwargs["tool_name"] == "emit_proofread"
    assert kwargs["tool_schema"] == PROOFREAD_SCHEMA
    assert "최고의" in kwargs["system"]
    assert "맞춤법" in kwargs["system"]


def test_proofread_passes_original_captions_in_user_prompt():
    client = MagicMock()
    client.call_tool.return_value = {"variants": []}
    captions = [
        {"label": "감성", "caption": "원문 1", "hashtags": []},
        {"label": "정보", "caption": "원문 2", "hashtags": []},
    ]
    proofread(client=client, captions=captions, brand_rules=BrandRules())
    user_prompt = client.call_tool.call_args.kwargs["user"]
    assert "원문 1" in user_prompt
    assert "원문 2" in user_prompt
