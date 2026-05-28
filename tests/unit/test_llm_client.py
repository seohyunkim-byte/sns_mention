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
