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

    # 기본 모델은 'gemini-2.5-flash-lite' — 현재 무료 등급에서 안정적으로 호출 가능한 유일한
    # 옵션. 'gemini-2.0-flash' 와 'gemini-2.5-flash' 는 free tier 한도가 0 또는 매우 낮아 팀 사용
    # 불가. 더 좋은 품질이 필요하면 환경변수 GEMINI_MODEL='gemini-2.5-flash' 로 덮어쓰고
    # Google AI Studio 결제(매우 저렴)를 활성화해야 한다.
    DEFAULT_MODEL = "gemini-2.5-flash-lite"

    def __init__(
        self,
        *,
        sdk: Any | None = None,
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
        max_tokens: int = 8192,
    ):
        if model is None:
            model = os.environ.get("GEMINI_MODEL", self.DEFAULT_MODEL)
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
        # Gemini 2.5 Flash 는 기본으로 "thinking" 토큰을 max_output_tokens 에서 소비한다.
        # 함수 호출 강제 시나리오에서는 reasoning 이 필요 없고, thinking 이 길어지면
        # function_call 을 발화하기 전에 토큰 한도가 차서 빈 응답이 나올 수 있다.
        # thinking_budget=0 으로 비활성화해서 출력 토큰 예산을 모두 실제 응답에 사용한다.
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            tools=[tool],
            tool_config=genai_types.ToolConfig(
                function_calling_config=genai_types.FunctionCallingConfig(
                    mode=genai_types.FunctionCallingConfigMode.ANY,
                    allowed_function_names=[tool_name],
                )
            ),
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
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

        # 진단 정보 — finish_reason 과 텍스트 내용을 에러 메시지에 포함시켜 어떤 상황인지 파악 가능하게.
        diag = _diagnose_no_function_call(response)
        logger.error("llm.call_tool no function_call model=%s tool=%s diag=%s",
                     self.model, tool_name, diag)
        raise LLMError(f"no function_call block in response ({diag})")


def _diagnose_no_function_call(response: Any) -> str:
    """function_call 누락 시 에러에 붙일 진단 문자열을 만든다."""
    if not getattr(response, "candidates", None):
        return "empty candidates"
    cand = response.candidates[0]
    parts: list[str] = []
    finish = getattr(cand, "finish_reason", None)
    if finish:
        parts.append(f"finish_reason={finish}")
    content = getattr(cand, "content", None)
    text_chunks: list[str] = []
    if content:
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text:
                text_chunks.append(text)
    if text_chunks:
        joined = "".join(text_chunks).strip()
        if len(joined) > 300:
            joined = joined[:300] + "..."
        parts.append(f"text={joined!r}")
    return " ".join(parts) or "empty response"
