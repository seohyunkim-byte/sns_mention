"""실제 Claude 호출 통합 테스트.

RUN_INTEGRATION=1 환경에서만 실행. 키 누락 시 자동 skip.
"""
from __future__ import annotations

import os

import pytest

from core.claude_client import ClaudeClient


pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> ClaudeClient:
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("RUN_INTEGRATION=1 필요")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY 필요")
    return ClaudeClient()


def test_call_tool_real_returns_schema_compliant_dict(client: ClaudeClient):
    schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string"}},
    }
    result = client.call_tool(
        system="간결히 답하라.",
        user="대한민국의 수도는 무엇인가? answer 필드로 도시명만 반환.",
        tool_name="emit_answer",
        tool_schema=schema,
    )
    assert isinstance(result, dict)
    assert "answer" in result
    assert "서울" in result["answer"]
