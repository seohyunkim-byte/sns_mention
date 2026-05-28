"""core/claude_client.py 단위 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.claude_client import ClaudeClient, ClaudeError


def _stub_anthropic_with_tool_response(payload: dict) -> MagicMock:
    """tool_use 형식의 응답을 반환하는 Anthropic SDK 모의."""
    sdk = MagicMock()
    response = MagicMock()
    response.stop_reason = "tool_use"
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_json"
    block.input = payload
    response.content = [block]
    sdk.messages.create.return_value = response
    return sdk


def _transient_error():
    """재시도 대상 예외 — 네트워크 일시 장애."""
    from anthropic import APIConnectionError

    return APIConnectionError(request=MagicMock())


def test_call_tool_returns_tool_input():
    sdk = _stub_anthropic_with_tool_response({"foo": "bar"})
    client = ClaudeClient(sdk=sdk, model="claude-sonnet-4-6")
    result = client.call_tool(
        system="sys",
        user="user",
        tool_name="emit_json",
        tool_schema={"type": "object", "properties": {"foo": {"type": "string"}}},
    )
    assert result == {"foo": "bar"}
    sdk.messages.create.assert_called_once()
    call_kwargs = sdk.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "emit_json"}


def test_call_tool_raises_when_no_tool_use_block():
    sdk = MagicMock()
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = []
    sdk.messages.create.return_value = response
    client = ClaudeClient(sdk=sdk)
    with pytest.raises(ClaudeError, match="no tool_use"):
        client.call_tool(system="s", user="u", tool_name="t", tool_schema={})


def test_call_tool_retries_on_transient_error_then_succeeds():
    sdk = MagicMock()
    response = MagicMock()
    response.stop_reason = "tool_use"
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_json"
    block.input = {"ok": True}
    response.content = [block]
    sdk.messages.create.side_effect = [_transient_error(), response]
    client = ClaudeClient(sdk=sdk, max_retries=2)
    result = client.call_tool(system="s", user="u", tool_name="emit_json", tool_schema={})
    assert result == {"ok": True}
    assert sdk.messages.create.call_count == 2


def test_call_tool_gives_up_after_max_retries():
    sdk = MagicMock()
    sdk.messages.create.side_effect = _transient_error()
    client = ClaudeClient(sdk=sdk, max_retries=2)
    with pytest.raises(ClaudeError, match="failed"):
        client.call_tool(system="s", user="u", tool_name="t", tool_schema={})
    assert sdk.messages.create.call_count == 2


def test_call_tool_does_not_retry_non_transient_error():
    """인증 등 4xx 오류는 즉시 실패해야 백오프 시간 낭비를 막는다."""
    from anthropic import AuthenticationError

    sdk = MagicMock()
    response = MagicMock()
    response.status_code = 401
    sdk.messages.create.side_effect = AuthenticationError(
        message="invalid key", response=response, body=None
    )
    client = ClaudeClient(sdk=sdk, max_retries=3)
    with pytest.raises(ClaudeError, match="failed"):
        client.call_tool(system="s", user="u", tool_name="t", tool_schema={})
    assert sdk.messages.create.call_count == 1


def test_init_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ClaudeError, match="missing"):
        ClaudeClient()
