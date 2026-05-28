"""Google Gemini SDK 의 단일 진입점.

이 파일만이 google.genai 를 import 한다. 재시도/로깅/모킹을 여기 모은다.

원래 Anthropic Claude 였으나 무료 등급 우선 방침에 따라 Gemini 2.5 Flash 로 전환.
인터페이스(`LLMClient.call_tool`)는 동일하게 유지하므로 호출부(`core.analyze`, `core.generate`)
는 import 만 바꾸면 된다.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# 일시적 오류만 재시도. 인증/요청 오류(ClientError, 4xx)는 즉시 실패해야 백오프 시간 낭비를 막는다.
_RETRYABLE = (genai_errors.ServerError, ConnectionError, TimeoutError)


class LLMError(Exception):
    """LLM 호출 실패."""


class LLMClient:
    """Gemini function-calling 기반 JSON 강제 응답 + 지수 백오프 재시도.

    단일 도구를 등록하고 tool_config 의 `mode="ANY"` + `allowed_function_names` 로
    그 도구 호출을 강제한다 — Claude 의 `tool_choice={"type": "tool", "name": ...}` 와 동일 의도.
    """

    DEFAULT_MODEL = "gemini-2.5-flash"

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
            key = (
                api_key
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
            )
            if not key:
                raise LLMError("GEMINI_API_KEY missing")
            sdk = genai.Client(api_key=key)
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
        """function calling 으로 JSON 출력 강제. 도구 입력 dict 를 반환."""

        # Gemini SDK 는 dict 를 Schema 로 자동 변환하지만 타입 힌트는 Schema|None 이라 cast 필요.
        # mode 도 Enum 이 정식이라 문자열 대신 Enum 값 사용.
        tool = genai_types.Tool(
            function_declarations=[
                genai_types.FunctionDeclaration(
                    name=tool_name,
                    description="Emit structured JSON output.",
                    parameters=tool_schema,  # type: ignore[arg-type]
                )
            ]
        )
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            tools=[tool],
            tool_config=genai_types.ToolConfig(
                function_calling_config=genai_types.FunctionCallingConfig(
                    mode=genai_types.FunctionCallingConfigMode.ANY,
                    allowed_function_names=[tool_name],
                )
            ),
            max_output_tokens=self.max_tokens,
        )

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _call() -> Any:
            return self._sdk.models.generate_content(
                model=self.model,
                contents=user,
                config=config,
            )

        logger.info("llm.call_tool model=%s tool=%s", self.model, tool_name)
        try:
            response = _call()
        except (genai_errors.APIError, ConnectionError, TimeoutError) as e:
            logger.error(
                "llm.call_tool failed model=%s tool=%s err=%s",
                self.model, tool_name, e,
            )
            raise LLMError(f"LLM call failed: {e}") from e

        for candidate in response.candidates or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", None) or []:
                fc = getattr(part, "function_call", None)
                if fc and fc.name == tool_name:
                    return dict(fc.args or {})
        raise LLMError("no function_call block in response")
