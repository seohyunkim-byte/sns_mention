"""Anthropic Claude SDK 의 단일 진입점.

이 파일만이 anthropic.Anthropic 을 import 한다. 재시도/로깅/모킹을 여기 모은다.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from anthropic import (
    Anthropic,
    APIConnectionError,
    APIError,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# 일시적 오류만 재시도. 인증/요청 오류는 즉시 실패해야 백오프 시간 낭비를 막는다.
_RETRYABLE = (APIConnectionError, RateLimitError, InternalServerError)


class ClaudeError(Exception):
    """Claude 호출 실패."""


class ClaudeClient:
    """tool_use 기반 JSON 강제 응답 + 지수 백오프 재시도."""

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(
        self,
        *,
        sdk: Any | None = None,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = 3,
        max_tokens: int = 4096,
    ):
        if sdk is None:
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise ClaudeError("ANTHROPIC_API_KEY missing")
            sdk = Anthropic(api_key=key)
        self._sdk = sdk
        self.model = model
        self.max_retries = max_retries
        self.max_tokens = max_tokens

    def call_tool(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """tool_use 로 JSON 출력 강제. 도구 입력 dict 를 반환."""

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _call() -> Any:
            return self._sdk.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                tools=[
                    {
                        "name": tool_name,
                        "description": "Emit structured JSON output.",
                        "input_schema": tool_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user}],
            )

        logger.info("claude.call_tool model=%s tool=%s", self.model, tool_name)
        try:
            response = _call()
        except APIError as e:
            logger.error("claude.call_tool failed model=%s tool=%s err=%s", self.model, tool_name, e)
            raise ClaudeError(f"Claude call failed: {e}") from e

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return dict(block.input)
        raise ClaudeError("no tool_use block in response")
