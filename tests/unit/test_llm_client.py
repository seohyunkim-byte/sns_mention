"""core/llm_client.py 단위 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.llm_client import LLMClient, LLMError


def _stub_sdk_with_function_call(tool_name: str, args: dict) -> MagicMock:
    """Gemini SDK 의 function-call 응답을 모사하는 모의."""
    sdk = MagicMock()
    response = MagicMock()
    part = MagicMock()
    fc = MagicMock()
    fc.name = tool_name
    fc.args = args
    part.function_call = fc
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response.candidates = [candidate]
    sdk.models.generate_content.return_value = response
    return sdk


def _stub_sdk_without_function_call() -> MagicMock:
    """function_call 이 없는 응답 (e.g., 모델이 일반 텍스트만 반환)."""
    sdk = MagicMock()
    response = MagicMock()
    part = MagicMock()
    part.function_call = None
    # text 도 명시적으로 None 으로 둬서 fallback JSON 추출 시도가 실패하도록.
    part.text = None
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response.candidates = [candidate]
    sdk.models.generate_content.return_value = response
    return sdk


def _stub_sdk_with_text_json(text_payload: str) -> MagicMock:
    """function_call 없이 텍스트로 JSON 을 반환한 응답 (Gemini 가 mode=ANY 무시한 경우)."""
    sdk = MagicMock()
    response = MagicMock()
    part = MagicMock()
    part.function_call = None
    part.text = text_payload
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response.candidates = [candidate]
    sdk.models.generate_content.return_value = response
    return sdk


def _transient_error() -> Exception:
    """재시도 대상 일시적 오류 — Gemini SDK 의 ServerError 모사."""
    from google.genai import errors as genai_errors

    response = MagicMock()
    response.status_code = 500
    # ServerError 생성자 시그니처: (code, response_json, response_obj)
    return genai_errors.ServerError(code=500, response_json={"error": {"message": "transient"}})


def test_call_tool_returns_function_call_args():
    sdk = _stub_sdk_with_function_call("emit_json", {"foo": "bar"})
    client = LLMClient(sdk=sdk, model="gemini-2.5-flash")
    result = client.call_tool(
        system="sys",
        user="user",
        tool_name="emit_json",
        tool_schema={"type": "object", "properties": {"foo": {"type": "string"}}},
    )
    assert result == {"foo": "bar"}
    sdk.models.generate_content.assert_called_once()
    kwargs = sdk.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["contents"] == "user"


def test_call_tool_raises_when_no_function_call_block():
    sdk = _stub_sdk_without_function_call()
    client = LLMClient(sdk=sdk)
    with pytest.raises(LLMError, match="no function_call"):
        client.call_tool(system="s", user="u", tool_name="t", tool_schema={"type": "object"})


def test_call_tool_retries_on_transient_error_then_succeeds():
    sdk = _stub_sdk_with_function_call("emit_json", {"ok": True})
    # 첫 호출은 ServerError, 두 번째 호출은 정상 응답
    successful_response = sdk.models.generate_content.return_value
    sdk.models.generate_content.side_effect = [_transient_error(), successful_response]

    client = LLMClient(sdk=sdk, max_retries=2)
    result = client.call_tool(system="s", user="u", tool_name="emit_json", tool_schema={"type": "object"})
    assert result == {"ok": True}
    assert sdk.models.generate_content.call_count == 2


def test_call_tool_gives_up_after_max_retries():
    sdk = MagicMock()
    sdk.models.generate_content.side_effect = _transient_error()
    client = LLMClient(sdk=sdk, max_retries=2)
    with pytest.raises(LLMError, match="failed"):
        client.call_tool(system="s", user="u", tool_name="t", tool_schema={"type": "object"})
    assert sdk.models.generate_content.call_count == 2


def test_call_tool_does_not_retry_non_transient_error():
    """ClientError(4xx, 예: 잘못된 키)는 즉시 실패해야 백오프 시간 낭비를 막는다."""
    from google.genai import errors as genai_errors

    sdk = MagicMock()
    sdk.models.generate_content.side_effect = genai_errors.ClientError(
        code=401, response_json={"error": {"message": "invalid api key"}}
    )
    client = LLMClient(sdk=sdk, max_retries=3)
    with pytest.raises(LLMError, match="failed"):
        client.call_tool(system="s", user="u", tool_name="t", tool_schema={"type": "object"})
    assert sdk.models.generate_content.call_count == 1


def test_init_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(LLMError, match="missing"):
        LLMClient()


# --- function_call fallback: 텍스트로 JSON 만 돌려주는 모델 응답 처리 ----------------

def test_call_tool_fallback_parses_json_from_markdown_fence():
    """Gemini가 mode=ANY 를 무시하고 ```json ... ``` 텍스트로 응답해도 동작해야 한다."""
    text = '```json\n{"variants": [{"label": "감성", "caption": "hi", "hashtags": []}]}\n```'
    sdk = _stub_sdk_with_text_json(text)
    client = LLMClient(sdk=sdk, model="gemini-2.5-flash-lite")
    result = client.call_tool(
        system="s", user="u", tool_name="emit_variants",
        tool_schema={"type": "object"},
    )
    assert "variants" in result
    assert result["variants"][0]["caption"] == "hi"


def test_call_tool_fallback_parses_bare_json():
    """펜스 없이 그냥 JSON 만 텍스트로 줘도 추출."""
    text = 'Sure, here it is:\n{"key": "value", "n": 42}\nDone.'
    sdk = _stub_sdk_with_text_json(text)
    client = LLMClient(sdk=sdk)
    result = client.call_tool(
        system="s", user="u", tool_name="t",
        tool_schema={"type": "object"},
    )
    assert result == {"key": "value", "n": 42}


def test_call_tool_fallback_handles_json_lang_tag():
    """```json (소문자 lang tag) 도 인식."""
    text = "결과:\n```json\n{\"foo\": \"bar\"}\n```"
    sdk = _stub_sdk_with_text_json(text)
    client = LLMClient(sdk=sdk)
    result = client.call_tool(
        system="s", user="u", tool_name="t",
        tool_schema={"type": "object"},
    )
    assert result == {"foo": "bar"}


def test_call_tool_fallback_returns_error_when_text_has_no_json():
    """텍스트만 있고 JSON 이 없으면 기존 에러 그대로 raise."""
    sdk = _stub_sdk_with_text_json("죄송합니다, 응답할 수 없습니다.")
    client = LLMClient(sdk=sdk)
    with pytest.raises(LLMError, match="no function_call"):
        client.call_tool(
            system="s", user="u", tool_name="t",
            tool_schema={"type": "object"},
        )


# --- 모델 체인 폴백 (429 / quota exhausted) ----------------------------------

def _quota_exhausted_error() -> Exception:
    """429 RESOURCE_EXHAUSTED 시뮬레이션."""
    from google.genai import errors as genai_errors

    return genai_errors.ClientError(
        code=429,
        response_json={
            "error": {
                "code": 429,
                "message": "Quota exceeded for free_tier_requests",
                "status": "RESOURCE_EXHAUSTED",
            }
        },
    )


def _success_function_call_response(args: dict) -> MagicMock:
    response = MagicMock()
    part = MagicMock()
    fc = MagicMock()
    fc.name = "t"
    fc.args = args
    part.function_call = fc
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response.candidates = [candidate]
    return response


def test_call_tool_falls_back_to_next_model_on_quota_exhausted():
    """첫 모델이 429 면 다음 모델로 자동 시도."""
    sdk = MagicMock()
    # 첫 호출은 quota error, 두 번째 호출은 성공
    sdk.models.generate_content.side_effect = [
        _quota_exhausted_error(),
        _success_function_call_response({"ok": True}),
    ]
    # GEMINI_MODEL 미설정 → DEFAULT_MODEL_CHAIN 사용
    import os as _os
    _os.environ.pop("GEMINI_MODEL", None)
    client = LLMClient(sdk=sdk, max_retries=1)
    # 모델 체인이 2개 이상이어야 fallback 테스트 의미가 있음
    assert len(client.model_chain) >= 2

    result = client.call_tool(
        system="s", user="u", tool_name="t",
        tool_schema={"type": "object"},
    )
    assert result == {"ok": True}
    # 두 번 호출되었어야 함 (첫 모델 quota → 두 번째 모델 시도)
    assert sdk.models.generate_content.call_count == 2
    # 두 번의 호출이 서로 다른 모델로 갔는지 확인
    models_used = [
        call.kwargs.get("model") for call in sdk.models.generate_content.call_args_list
    ]
    assert models_used[0] != models_used[1]


def test_call_tool_all_models_exhausted_raises():
    """모든 모델이 quota 초과면 명확한 에러 메시지로 raise."""
    sdk = MagicMock()
    sdk.models.generate_content.side_effect = _quota_exhausted_error()
    import os as _os
    _os.environ.pop("GEMINI_MODEL", None)
    client = LLMClient(sdk=sdk, max_retries=1)
    with pytest.raises(LLMError, match="체인의 모든 모델"):
        client.call_tool(
            system="s", user="u", tool_name="t",
            tool_schema={"type": "object"},
        )
    # 체인 길이만큼 호출됐어야 함
    assert sdk.models.generate_content.call_count == len(client.model_chain)


def test_call_tool_falls_back_on_404_not_found():
    """모델이 본 계정에서 404 (NOT_FOUND) 면 quota 와 똑같이 다음 모델로 폴백."""
    from google.genai import errors as genai_errors

    sdk = MagicMock()
    not_found = genai_errors.ClientError(
        code=404,
        response_json={
            "error": {
                "code": 404,
                "message": "models/gemini-1.5-flash-8b is not found for API version v1beta",
                "status": "NOT_FOUND",
            }
        },
    )
    sdk.models.generate_content.side_effect = [
        not_found,
        _success_function_call_response({"ok": True}),
    ]
    import os as _os
    _os.environ.pop("GEMINI_MODEL", None)
    client = LLMClient(sdk=sdk, max_retries=1)
    assert len(client.model_chain) >= 2

    result = client.call_tool(
        system="s", user="u", tool_name="t",
        tool_schema={"type": "object"},
    )
    assert result == {"ok": True}
    assert sdk.models.generate_content.call_count == 2


def test_call_tool_explicit_model_skips_fallback_chain():
    """사용자가 GEMINI_MODEL 명시 지정한 경우 단일 모델만 시도, 폴백 X."""
    sdk = MagicMock()
    sdk.models.generate_content.side_effect = _quota_exhausted_error()
    client = LLMClient(sdk=sdk, model="gemini-2.5-flash", max_retries=1)
    assert client.model_chain == ("gemini-2.5-flash",)
    with pytest.raises(LLMError):
        client.call_tool(
            system="s", user="u", tool_name="t",
            tool_schema={"type": "object"},
        )
    # 폴백 시도 없으므로 1번만 호출
    assert sdk.models.generate_content.call_count == 1


def test_call_tool_non_quota_error_does_not_trigger_fallback():
    """quota 외의 에러는 즉시 raise — 다음 모델 시도 X."""
    from google.genai import errors as genai_errors

    sdk = MagicMock()
    sdk.models.generate_content.side_effect = genai_errors.ClientError(
        code=401, response_json={"error": {"message": "invalid api key"}}
    )
    import os as _os
    _os.environ.pop("GEMINI_MODEL", None)
    client = LLMClient(sdk=sdk, max_retries=1)
    with pytest.raises(LLMError, match="failed"):
        client.call_tool(
            system="s", user="u", tool_name="t",
            tool_schema={"type": "object"},
        )
    # 인증 에러는 fallback 안 함 — 1번만 호출
    assert sdk.models.generate_content.call_count == 1
