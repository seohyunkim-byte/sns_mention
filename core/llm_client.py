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

    # Google 무료 등급이 모델별로 자주 변경되므로, 단일 모델 의존 X.
    # 429 (quota) 또는 404 (모델이 본 계정/리전에서 미제공) 시 다음 모델로 자동 폴백.
    # 환경변수 GEMINI_MODEL 이 설정되면 그 단일 모델만 사용 (폴백 X — 사용자 명시 선택 존중).
    DEFAULT_MODEL_CHAIN: tuple[str, ...] = (
        "gemini-2.0-flash-lite",   # 2.0 lite — 무료 한도 비교적 넓음
        "gemini-2.5-flash-lite",   # 2.5 lite — 일 20~1000회 (시점에 따라 변동)
        "gemini-flash-latest",     # 현재 권장 별칭 — Google 이 안정 모델 자동 선택
        "gemini-2.5-flash",        # 일 20회 (자주 한도지만 다른 모델 다 막혔으면 시도)
        "gemini-1.5-flash",        # 1.5 legacy — 일부 계정에서 가용
        "gemini-1.5-flash-8b",     # 1.5 8b — 일부 계정 가용 (없으면 404 → 다음으로)
    )
    DEFAULT_MODEL = DEFAULT_MODEL_CHAIN[0]  # 첫 모델 = 기본

    def __init__(
        self,
        *,
        sdk: Any | None = None,
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
        max_tokens: int = 8192,
    ):
        # 명시적 모델 지정 시(인자 또는 GEMINI_MODEL 환경변수) 단일 모델로만 시도.
        # 명시 안 했으면 DEFAULT_MODEL_CHAIN 전부 순차 시도.
        explicit_model = model or os.environ.get("GEMINI_MODEL")
        if explicit_model:
            self.model_chain: tuple[str, ...] = (explicit_model,)
        else:
            self.model_chain = self.DEFAULT_MODEL_CHAIN
        self.model = self.model_chain[0]  # 호환성 — 외부 코드 (예: model_version 메타) 에서 접근

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
        """function calling 으로 JSON 출력 강제. 도구 입력 dict 를 반환.

        model_chain 의 모델을 순서대로 시도. 429 (quota) 또는 404 (모델 미제공)
        시 다음 모델로 자동 폴백. 모든 모델이 막혔을 때만 LLMError.
        """
        last_recoverable_error: LLMError | None = None
        for model in self.model_chain:
            try:
                return self._call_one_model(
                    model=model,
                    system=system,
                    user=user,
                    tool_name=tool_name,
                    tool_schema=tool_schema,
                )
            except LLMError as e:
                if _should_fallback_to_next_model(e):
                    logger.warning(
                        "llm.call_tool model %s unavailable, falling back: %s",
                        model, e,
                    )
                    last_recoverable_error = e
                    continue
                raise
        # 모든 모델이 막힘
        raise LLMError(
            f"체인의 모든 모델이 사용 불가합니다. "
            f"마지막 에러: {last_recoverable_error}. "
            f"UTC 자정(한국 시간 오전 9시) 이후 한도가 리셋되면 재시도하거나, "
            f"GEMINI_MODEL secret 으로 특정 모델을 강제 지정하세요."
        )

    def _call_one_model(
        self,
        *,
        model: str,
        system: str,
        user: str,
        tool_name: str,
        tool_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """단일 모델로 1회 호출 + 결과 파싱. 폴백 없음."""
        # Gemini SDK 는 dict 를 Schema 로 자동 변환하지만 타입 힌트는 Schema|None 이라 cast 필요.
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
                model=model,
                contents=user,
                config=config,
            )

        logger.info("llm.call_tool model=%s tool=%s", model, tool_name)
        try:
            response = _call()
        except (genai_errors.APIError, ConnectionError, TimeoutError) as e:
            logger.error(
                "llm.call_tool failed model=%s tool=%s err=%s",
                model, tool_name, e,
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

        # Fallback — Gemini lite/flash 가 가끔 mode=ANY 를 무시하고 ```json ... ``` 텍스트로 응답.
        extracted = _extract_json_from_text(response)
        if extracted is not None:
            logger.warning(
                "llm.call_tool fallback: parsed JSON from text response model=%s tool=%s",
                model, tool_name,
            )
            return extracted

        diag = _diagnose_no_function_call(response)
        logger.error("llm.call_tool no function_call model=%s tool=%s diag=%s",
                     model, tool_name, diag)
        raise LLMError(f"no function_call block in response ({diag})")


def _should_fallback_to_next_model(error: Exception) -> bool:
    """체인의 다음 모델로 폴백해야 하는 에러인지 판단.

    포함 케이스:
      - 429 / RESOURCE_EXHAUSTED — quota 초과 (일시적, 다음 모델로 시도)
      - 404 NOT_FOUND — 해당 계정·리전에서 모델 미제공 (영구, 다음 모델로 시도)
      - "not supported for generateContent" — 모델이 이 작업 지원 안 함

    비포함 (즉시 raise) 케이스:
      - 401/403 — 인증 문제 (API 키 잘못)
      - 400 — 잘못된 요청 (스키마·페이로드 문제)
      - 500+ — 서버 오류는 tenacity 가 이미 재시도하므로 여기까지 오면 진짜 장애
    """
    msg = str(error)
    msg_lower = msg.lower()
    # quota
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
        return True
    if "exceeded your current quota" in msg_lower or "free_tier" in msg_lower:
        return True
    # model not found / not supported
    if "404" in msg or "NOT_FOUND" in msg:
        return True
    if "not found for api version" in msg_lower:
        return True
    if "not supported for generatecontent" in msg_lower:
        return True
    return False


# 하위 호환 — 외부 코드가 이전 함수명을 import 할 가능성 대비.
_is_quota_exhausted = _should_fallback_to_next_model


def _extract_json_from_text(response: Any) -> dict[str, Any] | None:
    """response 의 텍스트 파트에서 JSON 객체를 추출한다. 실패 시 None.

    ```json ... ``` 코드 펜스, 또는 펜스 없이 그냥 JSON 본문 두 경우 모두 시도.
    """
    import json as _json
    import re as _re

    text_chunks: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text:
                text_chunks.append(text)
    if not text_chunks:
        return None
    full_text = "".join(text_chunks)

    # 1) ```json ... ``` 또는 ``` ... ``` 펜스 내부 우선 시도
    fence_match = _re.search(r"```(?:json)?\s*\n?(.*?)```", full_text, _re.DOTALL)
    if fence_match:
        candidate_text = fence_match.group(1).strip()
        try:
            parsed = _json.loads(candidate_text)
            if isinstance(parsed, dict):
                return parsed
        except _json.JSONDecodeError:
            pass

    # 2) 펜스 없으면 첫 { 부터 마지막 } 까지 시도
    first = full_text.find("{")
    last = full_text.rfind("}")
    if first != -1 and last > first:
        candidate_text = full_text[first : last + 1]
        try:
            parsed = _json.loads(candidate_text)
            if isinstance(parsed, dict):
                return parsed
        except _json.JSONDecodeError:
            return None
    return None


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
