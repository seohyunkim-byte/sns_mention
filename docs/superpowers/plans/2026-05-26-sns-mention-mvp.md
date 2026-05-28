# 브랜드 맞춤형 인스타그램 멘션 자동 생성 프로그램 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit 1페이지 앱에서 브랜드 IG 톤을 학습해 Brief 를 3개 카피 변종(감성/정보/이벤트 강조)으로 자동 생성하는 MVP.

**Architecture:** Streamlit UI → 비즈니스 로직(core) → JSON 저장소(storage). 모든 Claude 호출은 `core/claude_client.py` 단일 진입점을 통과. 의존성 주입으로 테스트에서 모킹.

**Tech Stack:** Python 3.12+, Streamlit, Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`), Pydantic v2, instaloader (best-effort), tenacity, python-dotenv, pytest.

**Spec:** [docs/superpowers/specs/2026-05-26-sns-mention-design.md](../specs/2026-05-26-sns-mention-design.md)

---

## File Map

| 책임 | 파일 | 비고 |
|------|------|------|
| 진입점 | `app.py` | Streamlit, 사이드바 + 메인 라우팅만 |
| 데이터 모델 | `storage/models.py` | Pydantic v2 BrandProfile 트리 |
| 영속화 | `storage/repo.py` | JSON CRUD, slugify, 스키마 검증 |
| LLM 단일 진입점 | `core/claude_client.py` | tool_use JSON 강제, tenacity 재시도 |
| 수집 | `core/ingest.py` | paste 파서 + URL 파서 + instaloader 베스트-에포트 |
| 톤 분석 | `core/analyze.py` | 프롬프트 빌더 + extract_profile |
| 카피 생성 | `core/generate.py` | write_captions + proofread |
| 사이드바 UI | `ui/sidebar.py` | 브랜드 목록 + 등록 버튼 |
| 등록 UI | `ui/register_view.py` | 3-step 위저드 |
| 생성 UI | `ui/generate_view.py` | Brief 입력 + 3변종 표시 |
| 환경 | `pyproject.toml`, `.env.example`, `.gitignore` | uv 의존성 |
| 테스트 | `tests/unit/*`, `tests/integration/*`, `tests/conftest.py`, `tests/fixtures/*` | unit 은 Claude 모킹, integration 은 `-m integration` |

`core/ingest`·`analyze`·`generate` 는 서로 import 금지. `ui/*` 는 `core/*` 와 `storage/*` 만 import.

---

## Task 1: 프로젝트 스캐폴딩 (의존성·구조·설정)

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore` (추가)
- Create: `core/__init__.py`, `storage/__init__.py`, `ui/__init__.py`, `storage/data/brands/.gitkeep`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/conftest.py`
- Create: `pytest.ini`

- [ ] **Step 1: `pyproject.toml` 작성**

```toml
[project]
name = "sns-mention"
version = "0.1.0"
description = "브랜드 맞춤형 인스타그램 캡션 자동 생성기 (MVP)"
requires-python = ">=3.12"
dependencies = [
    "streamlit>=1.36",
    "anthropic>=0.45",
    "pydantic>=2.7",
    "instaloader>=4.13",
    "python-dotenv>=1.0",
    "tenacity>=8.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "ruff>=0.6",
    "mypy>=1.10",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict_optional = true
ignore_missing_imports = true
```

- [ ] **Step 2: `.env.example` 작성**

```
ANTHROPIC_API_KEY=sk-ant-...
RUN_INTEGRATION=0
```

- [ ] **Step 3: `.gitignore` 보강**

기존 `.gitignore` 끝에 다음 추가:

```
# Python
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Env
.env
sns_mention/

# Brand data (개인 데이터, 공유 금지)
storage/data/brands/*.json
!storage/data/brands/.gitkeep
```

- [ ] **Step 4: 패키지/디렉토리 골격 생성**

```powershell
# 빈 __init__.py 들
"" | Out-File -Encoding utf8 core\__init__.py
"" | Out-File -Encoding utf8 storage\__init__.py
"" | Out-File -Encoding utf8 ui\__init__.py
"" | Out-File -Encoding utf8 tests\__init__.py
"" | Out-File -Encoding utf8 tests\unit\__init__.py
"" | Out-File -Encoding utf8 tests\integration\__init__.py
New-Item -ItemType Directory -Force storage\data\brands | Out-Null
"" | Out-File -Encoding utf8 storage\data\brands\.gitkeep
```

- [ ] **Step 5: `tests/conftest.py` 작성**

```python
"""pytest 공통 픽스처."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """임시 storage/data/brands/ 디렉토리."""
    d = tmp_path / "brands"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def mock_claude_client() -> MagicMock:
    """ClaudeClient 모킹. 테스트마다 return_value 를 세팅해 사용."""
    return MagicMock()
```

- [ ] **Step 6: `pytest.ini` 작성**

```ini
[pytest]
testpaths = tests
markers =
    integration: requires real Claude API key, set RUN_INTEGRATION=1
addopts = -ra --strict-markers
```

- [ ] **Step 7: 의존성 설치 + 검증**

```powershell
& "C:\Users\MADUP\.local\bin\uv.exe" sync
.\sns_mention\Scripts\Activate.ps1
python -c "import streamlit, anthropic, pydantic, instaloader, tenacity; print('OK')"
pytest --collect-only
```

기대: `import` 전부 성공, pytest 가 0 tests 를 collect (테스트 아직 없음).

- [ ] **Step 8: 커밋**

```bash
git add pyproject.toml .env.example .gitignore core/ storage/ ui/ tests/ pytest.ini
git commit -m "chore: scaffold project structure and dependencies"
```

---

## Task 2: Pydantic 데이터 모델

**Files:**
- Create: `storage/models.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: 실패 테스트 작성 — 최소 BrandProfile**

`tests/unit/test_models.py`:

```python
"""storage/models.py 단위 테스트."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

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


def test_brand_profile_minimal_required_fields():
    profile = BrandProfile(
        meta=Meta(
            brand_name="Nike KR",
            slug="nike-kr",
            analyzed_at=datetime(2026, 5, 26, 10, 0, 0),
        ),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(),
        formatting=Formatting(),
    )
    assert profile.meta.brand_name == "Nike KR"
    assert profile.brand_rules.forbidden_phrases == []
    assert profile.example_posts == []


def test_meta_requires_brand_name_and_slug():
    with pytest.raises(ValidationError):
        Meta(brand_name="Nike KR", analyzed_at=datetime.now())  # slug 누락


def test_voice_humor_level_bounds():
    with pytest.raises(ValidationError):
        Voice(humor_level=6)


def test_must_use_name_default_note_empty():
    name = MustUseName(term="Nike")
    assert name.note == ""


def test_brand_rules_defaults_empty_lists():
    rules = BrandRules()
    assert rules.must_use_names == []
    assert rules.forbidden_phrases == []
    assert rules.tone_guardrails == []


def test_brand_profile_roundtrip_json():
    profile = BrandProfile(
        meta=Meta(
            brand_name="Nike KR",
            slug="nike-kr",
            analyzed_at=datetime(2026, 5, 26, 10, 0, 0),
        ),
        voice=Voice(register="casual", sentence_endings=["~해요"]),
        emoji=Emoji(top=["🔥"]),
        hashtag=Hashtag(signature=["#나이키"]),
        formatting=Formatting(),
        brand_rules=BrandRules(forbidden_phrases=["최고의"]),
        example_posts=["오늘은 어제보다 1km 더. 🔥"],
    )
    dumped = profile.model_dump_json()
    restored = BrandProfile.model_validate_json(dumped)
    assert restored == profile
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

```powershell
pytest tests/unit/test_models.py -v
```

기대: `ModuleNotFoundError: No module named 'storage.models'`

- [ ] **Step 3: `storage/models.py` 구현**

```python
"""브랜드 프로필 Pydantic 모델.

스펙 §2 의 JSON 스키마를 그대로 매핑한다.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MustUseName(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    note: str = ""


class BrandRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_use_names: list[MustUseName] = Field(default_factory=list)
    forbidden_phrases: list[str] = Field(default_factory=list)
    tone_guardrails: list[str] = Field(default_factory=list)


class Voice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    register: str = "casual"
    address_form: str = ""
    sentence_endings: list[str] = Field(default_factory=list)
    avg_length_chars: int = 0
    humor_level: int = Field(default=0, ge=0, le=5)
    emotion_level: int = Field(default=0, ge=0, le=5)
    signature_phrases: list[str] = Field(default_factory=list)


class Emoji(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avg_per_post: float = 0.0
    top: list[str] = Field(default_factory=list)
    placement: str = "none"


class Hashtag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avg_count: int = 0
    signature: list[str] = Field(default_factory=list)
    common: list[str] = Field(default_factory=list)


class Formatting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_breaks: str = "sparse"
    uses_caps: bool = False
    uses_bullet_markers: bool = False


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand_name: str
    slug: str
    ig_handle: str = ""
    source_url: str = ""
    analyzed_at: datetime
    post_count: int = 0
    model_version: str = ""


class BrandProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: Meta
    voice: Voice
    emoji: Emoji
    hashtag: Hashtag
    formatting: Formatting
    topics: list[str] = Field(default_factory=list)
    brand_rules: BrandRules = Field(default_factory=BrandRules)
    example_posts: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
pytest tests/unit/test_models.py -v
```

기대: 6 passed.

- [ ] **Step 5: 커밋**

```bash
git add storage/models.py tests/unit/test_models.py
git commit -m "feat(storage): add Pydantic models for BrandProfile"
```

---

## Task 3: JSON Repo (CRUD + slugify)

**Files:**
- Create: `storage/repo.py`
- Create: `tests/unit/test_repo.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_repo.py`:

```python
"""storage/repo.py 단위 테스트."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from storage.models import (
    BrandProfile,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    Voice,
)
from storage.repo import BrandRepo, RepoError


def _make_profile(name: str = "Nike KR", slug: str = "nike-kr") -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name=name, slug=slug, analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(),
        formatting=Formatting(),
    )


def test_slugify_basic_ascii():
    assert BrandRepo.slugify("Nike KR") == "nike-kr"


def test_slugify_korean_preserved():
    assert BrandRepo.slugify("마켓컬리") == "마켓컬리"


def test_slugify_strips_special_chars():
    assert BrandRepo.slugify("Nike @ KR!! 2026") == "nike-kr-2026"


def test_slugify_empty_string_fallback():
    assert BrandRepo.slugify("   ") == "brand"


def test_save_creates_json_file(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    profile = _make_profile()
    path = repo.save(profile)
    assert path == tmp_data_dir / "nike-kr.json"
    assert path.exists()


def test_load_returns_validated_model(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    profile = _make_profile()
    repo.save(profile)
    loaded = repo.load("nike-kr")
    assert loaded == profile


def test_load_missing_raises(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    with pytest.raises(RepoError, match="not found"):
        repo.load("missing")


def test_load_invalid_json_raises(tmp_data_dir: Path):
    (tmp_data_dir / "broken.json").write_text("{ not json", encoding="utf-8")
    repo = BrandRepo(tmp_data_dir)
    with pytest.raises(RepoError, match="invalid"):
        repo.load("broken")


def test_load_schema_violation_raises(tmp_data_dir: Path):
    (tmp_data_dir / "bad.json").write_text('{"meta": {}}', encoding="utf-8")
    repo = BrandRepo(tmp_data_dir)
    with pytest.raises(RepoError, match="schema"):
        repo.load("bad")


def test_list_returns_sorted_by_brand_name(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile("Zara", "zara"))
    repo.save(_make_profile("Adidas", "adidas"))
    repo.save(_make_profile("Nike KR", "nike-kr"))
    names = [p.meta.brand_name for p in repo.list()]
    assert names == ["Adidas", "Nike KR", "Zara"]


def test_list_skips_invalid_files_returns_warnings(tmp_data_dir: Path):
    (tmp_data_dir / "broken.json").write_text("not json", encoding="utf-8")
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile())
    profiles, warnings = repo.list_with_warnings()
    assert len(profiles) == 1
    assert any("broken" in w for w in warnings)


def test_delete_removes_file(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile())
    assert repo.delete("nike-kr") is True
    assert not (tmp_data_dir / "nike-kr.json").exists()


def test_delete_nonexistent_returns_false(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    assert repo.delete("ghost") is False


def test_unique_slug_appends_suffix_on_collision(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(_make_profile("Nike", "nike"))
    assert repo.unique_slug("nike") == "nike-2"
    repo.save(_make_profile("Nike (2)", "nike-2"))
    assert repo.unique_slug("nike") == "nike-3"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```powershell
pytest tests/unit/test_repo.py -v
```

기대: `ModuleNotFoundError: No module named 'storage.repo'`

- [ ] **Step 3: `storage/repo.py` 구현**

```python
"""브랜드 프로필 JSON 파일 저장소.

`storage/data/brands/{slug}.json` 한 파일 = 한 브랜드.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from .models import BrandProfile


class RepoError(Exception):
    """저장소 작업 실패."""


class BrandRepo:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slugify(name: str) -> str:
        s = name.strip().lower()
        s = re.sub(r"[^\w\s가-힣\-]", "", s)
        s = re.sub(r"\s+", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
        return s or "brand"

    def _path(self, slug: str) -> Path:
        return self.data_dir / f"{slug}.json"

    def exists(self, slug: str) -> bool:
        return self._path(slug).exists()

    def unique_slug(self, base_slug: str) -> str:
        if not self.exists(base_slug):
            return base_slug
        n = 2
        while self.exists(f"{base_slug}-{n}"):
            n += 1
        return f"{base_slug}-{n}"

    def save(self, profile: BrandProfile) -> Path:
        path = self._path(profile.meta.slug)
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, slug: str) -> BrandProfile:
        path = self._path(slug)
        if not path.exists():
            raise RepoError(f"brand '{slug}' not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise RepoError(f"invalid JSON in '{slug}': {e}") from e
        try:
            return BrandProfile.model_validate(data)
        except ValidationError as e:
            raise RepoError(f"schema violation in '{slug}': {e}") from e

    def list(self) -> list[BrandProfile]:
        profiles, _ = self.list_with_warnings()
        return profiles

    def list_with_warnings(self) -> tuple[list[BrandProfile], list[str]]:
        profiles: list[BrandProfile] = []
        warnings: list[str] = []
        for p in sorted(self.data_dir.glob("*.json")):
            try:
                profiles.append(self.load(p.stem))
            except RepoError as e:
                warnings.append(f"{p.name}: {e}")
        profiles.sort(key=lambda x: x.meta.brand_name.lower())
        return profiles, warnings

    def delete(self, slug: str) -> bool:
        path = self._path(slug)
        if not path.exists():
            return False
        path.unlink()
        return True
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
pytest tests/unit/test_repo.py -v
```

기대: 14 passed.

- [ ] **Step 5: 커밋**

```bash
git add storage/repo.py tests/unit/test_repo.py
git commit -m "feat(storage): add JSON-backed BrandRepo with slugify and validation"
```

---

## Task 4: Claude Client (tool_use JSON 강제 + 재시도)

**Files:**
- Create: `core/claude_client.py`
- Create: `tests/unit/test_claude_client.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_claude_client.py`:

```python
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
    from anthropic import APIError

    sdk = MagicMock()
    response = MagicMock()
    response.stop_reason = "tool_use"
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_json"
    block.input = {"ok": True}
    response.content = [block]
    sdk.messages.create.side_effect = [
        APIError("rate limit", request=MagicMock(), body=None),
        response,
    ]
    client = ClaudeClient(sdk=sdk, max_retries=2)
    result = client.call_tool(system="s", user="u", tool_name="emit_json", tool_schema={})
    assert result == {"ok": True}
    assert sdk.messages.create.call_count == 2


def test_call_tool_gives_up_after_max_retries():
    from anthropic import APIError

    sdk = MagicMock()
    sdk.messages.create.side_effect = APIError("rate limit", request=MagicMock(), body=None)
    client = ClaudeClient(sdk=sdk, max_retries=2)
    with pytest.raises(ClaudeError, match="failed after"):
        client.call_tool(system="s", user="u", tool_name="t", tool_schema={})
    assert sdk.messages.create.call_count == 2
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_claude_client.py -v
```

기대: ModuleNotFoundError.

- [ ] **Step 3: `core/claude_client.py` 구현**

```python
"""Anthropic Claude SDK 의 단일 진입점.

이 파일만이 anthropic.Anthropic 을 import 한다. 재시도/로깅/모킹을 여기 모은다.
"""
from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic, APIError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


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
            retry=retry_if_exception_type(APIError),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
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

        try:
            response = _call()
        except (APIError, RetryError) as e:
            raise ClaudeError(f"Claude call failed after {self.max_retries} attempts: {e}") from e

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return dict(block.input)
        raise ClaudeError("no tool_use block in response")
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
pytest tests/unit/test_claude_client.py -v
```

기대: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add core/claude_client.py tests/unit/test_claude_client.py
git commit -m "feat(core): add Claude client with tool_use JSON enforcement and retries"
```

---

## Task 5: Ingest — Paste 파서 + URL 파서

**Files:**
- Create: `core/ingest.py`
- Create: `tests/unit/test_ingest.py`

- [ ] **Step 1: 실패 테스트 작성 (paste / URL 부분만)**

`tests/unit/test_ingest.py`:

```python
"""core/ingest.py 단위 테스트 — paste/URL 파서."""
from __future__ import annotations

import pytest

from core.ingest import extract_ig_handle, parse_pasted_posts


def test_parse_pasted_posts_basic():
    text = "첫 게시물\n둘째 줄\n---\n두번째 게시물\n---\n세번째"
    assert parse_pasted_posts(text) == [
        "첫 게시물\n둘째 줄",
        "두번째 게시물",
        "세번째",
    ]


def test_parse_pasted_posts_strips_whitespace():
    text = "   첫 게시물   \n---\n   둘째   "
    assert parse_pasted_posts(text) == ["첫 게시물", "둘째"]


def test_parse_pasted_posts_drops_empty():
    text = "첫\n---\n\n\n---\n둘"
    assert parse_pasted_posts(text) == ["첫", "둘"]


def test_parse_pasted_posts_accepts_long_divider():
    text = "첫\n-------\n둘"
    assert parse_pasted_posts(text) == ["첫", "둘"]


def test_parse_pasted_posts_empty_string_returns_empty_list():
    assert parse_pasted_posts("") == []


def test_extract_ig_handle_clean_url():
    assert extract_ig_handle("https://www.instagram.com/nike/") == "nike"


def test_extract_ig_handle_with_query_string():
    assert extract_ig_handle("https://instagram.com/nike?hl=ko") == "nike"


def test_extract_ig_handle_at_prefix():
    assert extract_ig_handle("@nike_kr") == "nike_kr"


def test_extract_ig_handle_invalid_returns_none():
    assert extract_ig_handle("not a url") is None
    assert extract_ig_handle("") is None
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_ingest.py -v
```

기대: ModuleNotFoundError.

- [ ] **Step 3: `core/ingest.py` 구현 (paste/URL 부분)**

```python
"""인스타그램 게시물 수집.

두 가지 수집 경로:
  1. parse_pasted_posts: 마케터가 ---로 구분해 붙여넣은 텍스트
  2. crawl_instagram:    instaloader 베스트-에포트 크롤 (Task 6)
"""
from __future__ import annotations

import re
from urllib.parse import urlparse


class IngestError(Exception):
    """수집 실패."""


_DIVIDER_RE = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]+$")


def parse_pasted_posts(text: str) -> list[str]:
    """`---` (3 hyphens+) 라인으로 텍스트 블록 분리. 공백 strip 후 빈 블록 제거."""
    if not text:
        return []
    chunks = _DIVIDER_RE.split(text)
    return [c.strip() for c in chunks if c.strip()]


def extract_ig_handle(value: str) -> str | None:
    """IG URL 또는 @handle 에서 핸들만 추출. 못 뽑으면 None."""
    if not value:
        return None
    s = value.strip()
    if s.startswith("@"):
        candidate = s[1:]
        return candidate if _HANDLE_RE.match(candidate) else None
    try:
        parsed = urlparse(s if "://" in s else f"https://{s}")
    except ValueError:
        return None
    if "instagram.com" not in (parsed.netloc or ""):
        return None
    path = (parsed.path or "").strip("/")
    if not path:
        return None
    candidate = path.split("/", 1)[0]
    return candidate if _HANDLE_RE.match(candidate) else None
```

- [ ] **Step 4: 통과 확인**

```powershell
pytest tests/unit/test_ingest.py -v
```

기대: 9 passed.

- [ ] **Step 5: 커밋**

```bash
git add core/ingest.py tests/unit/test_ingest.py
git commit -m "feat(core): add paste parser and IG URL/handle extractor"
```

---

## Task 6: Ingest — Instaloader 크롤러 (best-effort)

**Files:**
- Modify: `core/ingest.py` (`crawl_instagram` 함수 추가)
- Modify: `tests/unit/test_ingest.py` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가**

`tests/unit/test_ingest.py` 끝에 추가:

```python
from unittest.mock import MagicMock, patch

from core.ingest import crawl_instagram


def _make_post(caption: str | None) -> MagicMock:
    m = MagicMock()
    m.caption = caption
    return m


@patch("core.ingest.instaloader")
def test_crawl_instagram_returns_captions(mock_il):
    profile = MagicMock()
    profile.get_posts.return_value = iter([
        _make_post("첫번째 캡션"),
        _make_post("두번째 캡션"),
    ])
    mock_il.Profile.from_username.return_value = profile
    mock_il.Instaloader.return_value = MagicMock()

    result = crawl_instagram("https://instagram.com/nike/", max_posts=10)
    assert result == ["첫번째 캡션", "두번째 캡션"]


@patch("core.ingest.instaloader")
def test_crawl_instagram_skips_empty_captions(mock_il):
    profile = MagicMock()
    profile.get_posts.return_value = iter([
        _make_post("실제 캡션"),
        _make_post(None),
        _make_post("  "),
    ])
    mock_il.Profile.from_username.return_value = profile
    mock_il.Instaloader.return_value = MagicMock()

    assert crawl_instagram("https://instagram.com/nike/", max_posts=10) == ["실제 캡션"]


@patch("core.ingest.instaloader")
def test_crawl_instagram_respects_max_posts(mock_il):
    profile = MagicMock()
    profile.get_posts.return_value = iter([
        _make_post(f"post {i}") for i in range(50)
    ])
    mock_il.Profile.from_username.return_value = profile
    mock_il.Instaloader.return_value = MagicMock()

    result = crawl_instagram("https://instagram.com/nike/", max_posts=5)
    assert len(result) == 5


@patch("core.ingest.instaloader")
def test_crawl_instagram_invalid_url_raises(mock_il):
    with pytest.raises(IngestError, match="invalid"):
        crawl_instagram("not a url")
    mock_il.Instaloader.assert_not_called()


@patch("core.ingest.instaloader")
def test_crawl_instagram_wraps_loader_errors(mock_il):
    mock_il.Profile.from_username.side_effect = Exception("login required")
    mock_il.Instaloader.return_value = MagicMock()

    with pytest.raises(IngestError, match="login required"):
        crawl_instagram("https://instagram.com/nike/")
```

`tests/unit/test_ingest.py` 상단 import 에 `IngestError` 도 추가:

```python
from core.ingest import IngestError, extract_ig_handle, parse_pasted_posts
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_ingest.py -v
```

기대: 새 테스트 5개 실패 (`crawl_instagram` 없음).

- [ ] **Step 3: `core/ingest.py` 에 `crawl_instagram` 추가**

`core/ingest.py` 끝에 추가:

```python
import instaloader  # noqa: E402  (Task 6 추가)


def crawl_instagram(url_or_handle: str, max_posts: int = 30) -> list[str]:
    """베스트-에포트 IG 캡션 크롤. 실패 시 IngestError 발생.

    인스타그램 정책상 자주 깨진다. 호출부는 반드시 try/except 로 받고
    paste fallback UI 로 전환해야 한다.
    """
    handle = extract_ig_handle(url_or_handle)
    if not handle:
        raise IngestError(f"invalid IG URL or handle: {url_or_handle!r}")

    try:
        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
        )
        profile = instaloader.Profile.from_username(loader.context, handle)
        captions: list[str] = []
        for post in profile.get_posts():
            if len(captions) >= max_posts:
                break
            caption = (post.caption or "").strip()
            if caption:
                captions.append(caption)
        return captions
    except IngestError:
        raise
    except Exception as e:  # instaloader 의 모든 예외를 단일 타입으로 압축
        raise IngestError(str(e)) from e
```

- [ ] **Step 4: 통과 확인**

```powershell
pytest tests/unit/test_ingest.py -v
```

기대: 14 passed.

- [ ] **Step 5: 커밋**

```bash
git add core/ingest.py tests/unit/test_ingest.py
git commit -m "feat(core): add best-effort Instagram crawler via instaloader"
```

---

## Task 7: Analyze — 톤 프로필 추출

**Files:**
- Create: `core/analyze.py`
- Create: `tests/unit/test_analyze.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_analyze.py`:

```python
"""core/analyze.py 단위 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from core.analyze import ANALYZE_SCHEMA, build_analyze_prompt, extract_profile
from storage.models import BrandRules, MustUseName


def test_build_analyze_prompt_includes_brand_name_and_posts():
    system, user = build_analyze_prompt(
        posts=["게시물 1", "게시물 2"],
        brand_name="Nike KR",
        forbidden_phrases=["최고의"],
    )
    assert "톤앤매너" in system
    assert "Nike KR" in user
    assert "게시물 1" in user
    assert "게시물 2" in user
    assert "최고의" in user


def test_build_analyze_prompt_handles_empty_forbidden():
    system, user = build_analyze_prompt(posts=["x"], brand_name="B", forbidden_phrases=[])
    assert "Nike" not in user
    assert "B" in user


def test_extract_profile_calls_client_with_schema():
    client = MagicMock()
    client.call_tool.return_value = {
        "voice": {
            "register": "casual",
            "address_form": "여러분",
            "sentence_endings": ["~해요"],
            "avg_length_chars": 80,
            "humor_level": 2,
            "emotion_level": 4,
            "signature_phrases": ["Just Do It"],
        },
        "emoji": {"avg_per_post": 0.4, "top": ["🔥"], "placement": "end_of_sentence"},
        "hashtag": {"avg_count": 6, "signature": ["#나이키"], "common": ["#운동"]},
        "formatting": {"line_breaks": "frequent", "uses_caps": False, "uses_bullet_markers": False},
        "topics": ["러닝"],
        "example_posts": ["오늘은 어제보다 1km 더."],
    }

    result = extract_profile(
        client=client,
        posts=["오늘은 어제보다 1km 더."],
        brand_name="Nike KR",
        brand_rules=BrandRules(forbidden_phrases=["최고의"]),
    )

    assert result["voice"]["register"] == "casual"
    assert result["topics"] == ["러닝"]
    client.call_tool.assert_called_once()
    kwargs = client.call_tool.call_args.kwargs
    assert kwargs["tool_name"] == "emit_profile"
    assert kwargs["tool_schema"] == ANALYZE_SCHEMA


def test_extract_profile_passes_must_use_names_in_prompt():
    client = MagicMock()
    client.call_tool.return_value = {
        "voice": {"register": "casual", "address_form": "", "sentence_endings": [],
                  "avg_length_chars": 0, "humor_level": 0, "emotion_level": 0, "signature_phrases": []},
        "emoji": {"avg_per_post": 0.0, "top": [], "placement": "none"},
        "hashtag": {"avg_count": 0, "signature": [], "common": []},
        "formatting": {"line_breaks": "sparse", "uses_caps": False, "uses_bullet_markers": False},
        "topics": [],
        "example_posts": [],
    }

    rules = BrandRules(
        must_use_names=[MustUseName(term="Nike", note="대문자 N")],
        forbidden_phrases=["최고의"],
    )
    extract_profile(client=client, posts=["x"], brand_name="Nike KR", brand_rules=rules)

    user_prompt = client.call_tool.call_args.kwargs["user"]
    assert "Nike" in user_prompt
    assert "대문자 N" in user_prompt
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_analyze.py -v
```

기대: ModuleNotFoundError.

- [ ] **Step 3: `core/analyze.py` 구현**

```python
"""인스타그램 게시물 묶음에서 브랜드 톤 프로필을 추출한다.

이 모듈은 `core.claude_client.ClaudeClient` 만 의존한다. ingest/generate 와 상호 import 금지.
"""
from __future__ import annotations

from typing import Any

from core.claude_client import ClaudeClient
from storage.models import BrandRules


ANALYZE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["voice", "emoji", "hashtag", "formatting", "topics", "example_posts"],
    "properties": {
        "voice": {
            "type": "object",
            "required": [
                "register", "address_form", "sentence_endings",
                "avg_length_chars", "humor_level", "emotion_level", "signature_phrases",
            ],
            "properties": {
                "register": {"type": "string"},
                "address_form": {"type": "string"},
                "sentence_endings": {"type": "array", "items": {"type": "string"}},
                "avg_length_chars": {"type": "integer", "minimum": 0},
                "humor_level": {"type": "integer", "minimum": 0, "maximum": 5},
                "emotion_level": {"type": "integer", "minimum": 0, "maximum": 5},
                "signature_phrases": {"type": "array", "items": {"type": "string"}},
            },
        },
        "emoji": {
            "type": "object",
            "required": ["avg_per_post", "top", "placement"],
            "properties": {
                "avg_per_post": {"type": "number", "minimum": 0},
                "top": {"type": "array", "items": {"type": "string"}},
                "placement": {"type": "string"},
            },
        },
        "hashtag": {
            "type": "object",
            "required": ["avg_count", "signature", "common"],
            "properties": {
                "avg_count": {"type": "integer", "minimum": 0},
                "signature": {"type": "array", "items": {"type": "string"}},
                "common": {"type": "array", "items": {"type": "string"}},
            },
        },
        "formatting": {
            "type": "object",
            "required": ["line_breaks", "uses_caps", "uses_bullet_markers"],
            "properties": {
                "line_breaks": {"type": "string"},
                "uses_caps": {"type": "boolean"},
                "uses_bullet_markers": {"type": "boolean"},
            },
        },
        "topics": {"type": "array", "items": {"type": "string"}},
        "example_posts": {"type": "array", "items": {"type": "string"}},
    },
}


_SYSTEM = """\
당신은 10년 차 브랜드 톤앤매너 분석 전문가다.
주어진 인스타그램 게시물들을 읽고 브랜드의 일관된 보이스를 JSON 으로 추출하라.

규칙:
- 추측 금지. 게시물에서 확인되는 패턴만 기록.
- 빈도가 낮은 표현(1~2회)은 시그니처로 보지 말 것.
- 금지어 목록과 겹치는 표현이 포함된 게시물은 example_posts 에서 제외하라.
- example_posts 는 톤이 가장 대표적인 3~5개만 발췌."""


def build_analyze_prompt(
    *,
    posts: list[str],
    brand_name: str,
    forbidden_phrases: list[str],
    must_use_names: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """(system, user) 프롬프트 페어 반환."""
    must_use_names = must_use_names or []
    lines: list[str] = [f"브랜드명: {brand_name}"]
    if forbidden_phrases:
        lines.append(f"금지 표현 (제외 대상): {', '.join(forbidden_phrases)}")
    if must_use_names:
        formatted = "; ".join(f"{term} ({note})" if note else term for term, note in must_use_names)
        lines.append(f"정확 표기 명칭: {formatted}")
    lines.append(f"게시물 ({len(posts)}개):")
    for i, post in enumerate(posts, 1):
        lines.append("---")
        lines.append(post)
    lines.append("---")
    lines.append("위 자료에서 패턴을 추출하여 emit_profile 도구로 JSON 을 반환하라.")
    return _SYSTEM, "\n".join(lines)


def extract_profile(
    *,
    client: ClaudeClient,
    posts: list[str],
    brand_name: str,
    brand_rules: BrandRules,
) -> dict[str, Any]:
    """톤 프로필을 추출해 dict 반환. 호출부에서 Meta 등을 합쳐 BrandProfile 완성."""
    system, user = build_analyze_prompt(
        posts=posts,
        brand_name=brand_name,
        forbidden_phrases=brand_rules.forbidden_phrases,
        must_use_names=[(m.term, m.note) for m in brand_rules.must_use_names],
    )
    return client.call_tool(
        system=system,
        user=user,
        tool_name="emit_profile",
        tool_schema=ANALYZE_SCHEMA,
    )
```

- [ ] **Step 4: 통과 확인**

```powershell
pytest tests/unit/test_analyze.py -v
```

기대: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add core/analyze.py tests/unit/test_analyze.py
git commit -m "feat(core): add tone profile analyzer with Claude tool_use schema"
```

---

## Task 8: Generate — Caption Writer (1차 호출)

**Files:**
- Create: `core/generate.py`
- Create: `tests/unit/test_generate.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_generate.py`:

```python
"""core/generate.py 단위 테스트 — 카피 작성."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from core.generate import GENERATE_SCHEMA, build_generate_prompt, write_captions
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
    profile = _make_profile()
    system, _ = build_generate_prompt(profile=profile, brief="x", variants=["감성"])
    assert "감성" in system
    assert "정보" not in system
    assert "이벤트 강조" not in system


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
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_generate.py -v
```

기대: ModuleNotFoundError.

- [ ] **Step 3: `core/generate.py` 구현 (write_captions 부분만)**

```python
"""브랜드 프로필 + Brief → 3개 카피 변종 + 한글 맞춤법 교정.

이 모듈은 `core.claude_client.ClaudeClient` 만 의존한다. ingest/analyze 와 상호 import 금지.
"""
from __future__ import annotations

from typing import Any

from core.claude_client import ClaudeClient
from storage.models import BrandProfile


_VARIANT_DESCRIPTIONS = {
    "감성": "감정·스토리·공감 중심",
    "정보": "혜택·스펙·이유 중심",
    "이벤트 강조": "한정성·CTA·기간 강조",
}


GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["variants"],
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "caption", "hashtags"],
                "properties": {
                    "label": {"type": "string"},
                    "caption": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def _format_must_use(profile: BrandProfile) -> str:
    rules = profile.brand_rules.must_use_names
    if not rules:
        return "(없음)"
    return "; ".join(f"{m.term} ({m.note})" if m.note else m.term for m in rules)


def _format_variant_block(variants: list[str]) -> str:
    lines = []
    for i, label in enumerate(variants, 1):
        desc = _VARIANT_DESCRIPTIONS.get(label, label)
        lines.append(f"   - 변종 {i} ({label}): {desc}")
    return "\n".join(lines)


def build_generate_prompt(
    *,
    profile: BrandProfile,
    brief: str,
    variants: list[str],
    extra_instruction: str = "",
) -> tuple[str, str]:
    """(system, user) 프롬프트 페어 반환."""
    forbidden = ", ".join(profile.brand_rules.forbidden_phrases) or "(없음)"
    must_use = _format_must_use(profile)
    variant_block = _format_variant_block(variants)

    system = f"""\
당신은 {profile.meta.brand_name} 의 인스타그램 카피라이터다.
아래 브랜드 프로필을 완벽히 학습하여, Brief 를 카피 변종으로 작성하라.

[중요 제약 — 위반 시 실격]
1. 다음 표현은 절대 사용 금지: {forbidden}
2. 다음 명칭은 정확히 이 표기로만: {must_use}
3. 국립국어원 표준 맞춤법·띄어쓰기 엄격 준수.
4. Brief 에 없는 사실(가격·기간·수량) 임의 생성 금지.
5. 변종별 차별점:
{variant_block}

emit_variants 도구로 JSON 을 반환하라."""

    voice = profile.voice
    emoji = profile.emoji
    hashtag = profile.hashtag
    formatting = profile.formatting

    user_parts: list[str] = []
    user_parts.append("=== 브랜드 프로필 ===")
    user_parts.append(
        f"- register: {voice.register}\n"
        f"- address_form: {voice.address_form}\n"
        f"- sentence_endings: {voice.sentence_endings}\n"
        f"- avg_length_chars: {voice.avg_length_chars}\n"
        f"- humor_level: {voice.humor_level}\n"
        f"- emotion_level: {voice.emotion_level}\n"
        f"- emoji top: {emoji.top}, avg_per_post: {emoji.avg_per_post}, placement: {emoji.placement}\n"
        f"- hashtag signature: {hashtag.signature}\n"
        f"- hashtag common: {hashtag.common}\n"
        f"- avg hashtag count: {hashtag.avg_count}\n"
        f"- formatting: line_breaks={formatting.line_breaks}, "
        f"uses_caps={formatting.uses_caps}, uses_bullet_markers={formatting.uses_bullet_markers}"
    )
    user_parts.append("\n=== 시그니처 표현 (자연스럽게 1~2개 활용) ===")
    user_parts.append(", ".join(voice.signature_phrases) or "(없음)")

    user_parts.append("\n=== 대표 게시물 (이 톤으로 써라) ===")
    for ex in profile.example_posts:
        user_parts.append("---")
        user_parts.append(ex)

    user_parts.append("\n=== 톤 가드레일 ===")
    user_parts.append("\n".join(f"- {g}" for g in profile.brand_rules.tone_guardrails) or "(없음)")

    user_parts.append("\n=== Brief ===")
    user_parts.append(brief)

    if extra_instruction:
        user_parts.append("\n=== 추가 지시 (이 변종만) ===")
        user_parts.append(extra_instruction)

    user_parts.append(f"\n=== 작성할 변종 ({len(variants)}개) ===")
    user_parts.append(", ".join(variants))

    return system, "\n".join(user_parts)


def write_captions(
    *,
    client: ClaudeClient,
    profile: BrandProfile,
    brief: str,
    variants: list[str] | None = None,
    extra_instruction: str = "",
) -> list[dict[str, Any]]:
    """3개 변종(또는 지정된 변종) 카피를 작성해 리스트 반환."""
    variants = variants or ["감성", "정보", "이벤트 강조"]
    system, user = build_generate_prompt(
        profile=profile, brief=brief, variants=variants, extra_instruction=extra_instruction,
    )
    result = client.call_tool(
        system=system,
        user=user,
        tool_name="emit_variants",
        tool_schema=GENERATE_SCHEMA,
    )
    return list(result.get("variants", []))
```

- [ ] **Step 4: 통과 확인**

```powershell
pytest tests/unit/test_generate.py -v
```

기대: 5 passed.

- [ ] **Step 5: 커밋**

```bash
git add core/generate.py tests/unit/test_generate.py
git commit -m "feat(core): add caption writer with structured tone constraints"
```

---

## Task 9: Generate — Proofread (2차 호출, 한글 맞춤법)

**Files:**
- Modify: `core/generate.py` (`proofread` 함수 추가)
- Modify: `tests/unit/test_generate.py` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가**

`tests/unit/test_generate.py` 끝에 추가:

```python
from core.generate import PROOFREAD_SCHEMA, proofread


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
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_generate.py -v
```

기대: 새 테스트 2개 실패.

- [ ] **Step 3: `core/generate.py` 에 `proofread` 추가**

먼저 `core/generate.py` 최상단의 import 한 줄을 다음과 같이 교체:

기존:
```python
from storage.models import BrandProfile
```

교체:
```python
from storage.models import BrandProfile, BrandRules
```

그리고 파일 끝에 다음 코드를 추가:

```python
PROOFREAD_SCHEMA: dict[str, Any] = GENERATE_SCHEMA  # 동일 구조


def _format_must_use_from_rules(rules: BrandRules) -> str:
    items = rules.must_use_names
    if not items:
        return "(없음)"
    return "; ".join(f"{m.term} ({m.note})" if m.note else m.term for m in items)


def proofread(
    *,
    client: ClaudeClient,
    captions: list[dict[str, Any]],
    brand_rules: BrandRules,
) -> list[dict[str, Any]]:
    """카피 3개를 받아 한글 맞춤법·금지어·정확표기 교정 후 동일 구조로 반환."""
    forbidden = ", ".join(brand_rules.forbidden_phrases) or "(없음)"
    must_use = _format_must_use_from_rules(brand_rules)

    system = f"""\
당신은 한국어 교정 전문가다.
아래 카피들을 검토하여 다음만 수정하라:
1. 맞춤법·띄어쓰기 오류 (국립국어원 기준)
2. 자주 틀리는 케이스: 되/돼, 안/않, 률/율, 어색한 외래어 표기
3. 금지 표현 [{forbidden}] 포함 시 자연스럽게 치환
4. 정확 표기 [{must_use}] 위반 시 교정

수정 없으면 원문 그대로 반환. 의역·재창작·톤 변경 금지. 오직 교정만.
같은 label·hashtags 를 유지하고 caption 만 손볼 것."""

    user_parts: list[str] = []
    for c in captions:
        user_parts.append(f"[{c.get('label', '')}]")
        user_parts.append(c.get("caption", ""))
        user_parts.append("---")
    user_parts.append("emit_proofread 도구로 동일 JSON 구조를 반환하라.")

    result = client.call_tool(
        system=system,
        user="\n".join(user_parts),
        tool_name="emit_proofread",
        tool_schema=PROOFREAD_SCHEMA,
    )
    return list(result.get("variants", []))
```

- [ ] **Step 4: 통과 확인**

```powershell
pytest tests/unit/test_generate.py -v
```

기대: 7 passed (5 + 2).

- [ ] **Step 5: 커밋**

```bash
git add core/generate.py tests/unit/test_generate.py
git commit -m "feat(core): add Korean spellcheck/forbidden-word proofread pass"
```

---

## Task 10: Streamlit 진입점 + 사이드바

**Files:**
- Create: `app.py`
- Create: `ui/sidebar.py`
- Create: `tests/unit/test_sidebar.py`

- [ ] **Step 1: 사이드바 로직 테스트 작성 (UI 렌더링 제외, 순수 로직만)**

`tests/unit/test_sidebar.py`:

```python
"""ui/sidebar.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from storage.models import (
    BrandProfile,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    Voice,
)
from storage.repo import BrandRepo
from ui.sidebar import load_brand_options


def test_load_brand_options_returns_sorted_with_warnings(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    repo.save(
        BrandProfile(
            meta=Meta(brand_name="Zara", slug="zara", analyzed_at=datetime(2026, 5, 26)),
            voice=Voice(), emoji=Emoji(), hashtag=Hashtag(), formatting=Formatting(),
        )
    )
    repo.save(
        BrandProfile(
            meta=Meta(brand_name="Adidas", slug="adidas", analyzed_at=datetime(2026, 5, 26)),
            voice=Voice(), emoji=Emoji(), hashtag=Hashtag(), formatting=Formatting(),
        )
    )
    (tmp_data_dir / "broken.json").write_text("not json", encoding="utf-8")

    options, warnings = load_brand_options(repo)
    assert [o.meta.brand_name for o in options] == ["Adidas", "Zara"]
    assert any("broken" in w for w in warnings)


def test_load_brand_options_empty_dir(tmp_data_dir: Path):
    repo = BrandRepo(tmp_data_dir)
    options, warnings = load_brand_options(repo)
    assert options == []
    assert warnings == []
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_sidebar.py -v
```

기대: ModuleNotFoundError.

- [ ] **Step 3: `ui/sidebar.py` 구현**

```python
"""사이드바 — 브랜드 목록 + 신규 등록 버튼.

순수 로직(`load_brand_options`)은 별도 함수로 빼서 단위 테스트 가능.
Streamlit 렌더링(`render_sidebar`)은 호출부에서 사용.
"""
from __future__ import annotations

import streamlit as st

from storage.models import BrandProfile
from storage.repo import BrandRepo


def load_brand_options(repo: BrandRepo) -> tuple[list[BrandProfile], list[str]]:
    """저장된 브랜드 프로필 목록과 로드 경고를 반환."""
    return repo.list_with_warnings()


def render_sidebar(repo: BrandRepo) -> None:
    """사이드바 렌더. 세션 상태 키: `current_slug`, `mode` ('register' | 'generate')."""
    with st.sidebar:
        st.title("📚 브랜드")
        profiles, warnings = load_brand_options(repo)

        for w in warnings:
            st.warning(f"⚠️ {w}")

        if not profiles:
            st.caption("등록된 브랜드가 없습니다.")
        else:
            for p in profiles:
                if st.button(p.meta.brand_name, key=f"brand-{p.meta.slug}", use_container_width=True):
                    st.session_state.current_slug = p.meta.slug
                    st.session_state.mode = "generate"
                    st.rerun()

        st.divider()
        if st.button("＋ 새 브랜드 등록", use_container_width=True, type="primary"):
            st.session_state.current_slug = None
            st.session_state.mode = "register"
            st.session_state.register_step = 1
            st.rerun()
```

- [ ] **Step 4: `app.py` 구현 (라우팅만, 상세 화면은 Task 11~12에서)**

```python
"""Streamlit 진입점.

세션 상태:
  - `mode`: 'register' | 'generate' | None
  - `current_slug`: 선택된 브랜드 slug (generate 모드에서)
  - `register_step`: 1 | 2 | 3 (register 모드 위저드 단계)
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from storage.repo import BrandRepo
from ui.sidebar import render_sidebar

load_dotenv()

st.set_page_config(page_title="SNS Mention", page_icon="📝", layout="wide")

DATA_DIR = Path(__file__).parent / "storage" / "data" / "brands"


def _init_state() -> None:
    st.session_state.setdefault("mode", None)
    st.session_state.setdefault("current_slug", None)
    st.session_state.setdefault("register_step", 1)


def main() -> None:
    _init_state()
    repo = BrandRepo(DATA_DIR)
    render_sidebar(repo)

    mode = st.session_state.mode
    if mode == "register":
        st.header("새 브랜드 등록 (Task 11에서 구현)")
        st.info("3-step wizard 가 이 자리에 들어갑니다.")
    elif mode == "generate":
        st.header(f"카피 생성 — {st.session_state.current_slug} (Task 12에서 구현)")
        st.info("Brief 입력 + 3변종 출력이 이 자리에 들어갑니다.")
    else:
        st.title("브랜드 맞춤형 인스타그램 캡션 생성기")
        st.write("왼쪽 사이드바에서 브랜드를 선택하거나 새로 등록하세요.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 통과 + 수동 smoke**

```powershell
pytest tests/unit/test_sidebar.py -v
.\sns_mention\Scripts\Activate.ps1
streamlit run app.py
```

브라우저에서:
- 빈 사이드바 + "＋ 새 브랜드 등록" 버튼 보이는지
- 클릭 시 메인이 "Task 11에서 구현" 텍스트로 바뀌는지

수동 확인 후 Ctrl+C 로 streamlit 종료.

- [ ] **Step 6: 커밋**

```bash
git add app.py ui/sidebar.py tests/unit/test_sidebar.py
git commit -m "feat(ui): add Streamlit entry point and sidebar with brand list"
```

---

## Task 11: 등록 화면 — 3-step Wizard

**Files:**
- Create: `ui/register_view.py`
- Modify: `app.py` (register_view 연결)
- Create: `tests/unit/test_register_view.py`

- [ ] **Step 1: 비-UI 로직 테스트 작성**

`tests/unit/test_register_view.py`:

```python
"""ui/register_view.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from storage.models import BrandRules, MustUseName
from ui.register_view import (
    parse_must_use_input,
    parse_rule_list_input,
    run_analysis,
)


def test_parse_rule_list_input_basic():
    text = "최고의\n1등\n\n  유일한  "
    assert parse_rule_list_input(text) == ["최고의", "1등", "유일한"]


def test_parse_rule_list_input_empty():
    assert parse_rule_list_input("") == []


def test_parse_must_use_input_with_notes():
    text = "Nike | 영문 대문자 N\n에어 조던 | 띄어쓰기 필수\n구두점없음"
    result = parse_must_use_input(text)
    assert result == [
        MustUseName(term="Nike", note="영문 대문자 N"),
        MustUseName(term="에어 조던", note="띄어쓰기 필수"),
        MustUseName(term="구두점없음", note=""),
    ]


def test_parse_must_use_input_skips_blank_lines():
    text = "Nike\n\n\n에어 조던"
    assert parse_must_use_input(text) == [
        MustUseName(term="Nike", note=""),
        MustUseName(term="에어 조던", note=""),
    ]


def test_run_analysis_builds_profile_dict():
    client = MagicMock()
    client.call_tool.return_value = {
        "voice": {"register": "casual", "address_form": "", "sentence_endings": [],
                  "avg_length_chars": 50, "humor_level": 0, "emotion_level": 0, "signature_phrases": []},
        "emoji": {"avg_per_post": 0.0, "top": [], "placement": "none"},
        "hashtag": {"avg_count": 0, "signature": [], "common": []},
        "formatting": {"line_breaks": "sparse", "uses_caps": False, "uses_bullet_markers": False},
        "topics": [],
        "example_posts": ["대표 게시물"],
    }
    rules = BrandRules(forbidden_phrases=["x"])
    posts = ["게시물 1", "게시물 2"]
    result = run_analysis(
        client=client,
        posts=posts,
        brand_name="Nike KR",
        brand_rules=rules,
    )
    assert result["voice"]["register"] == "casual"
    assert result["example_posts"] == ["대표 게시물"]
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_register_view.py -v
```

기대: ModuleNotFoundError.

- [ ] **Step 3: `ui/register_view.py` 구현**

```python
"""신규 브랜드 등록 3-step 위저드.

비-UI 헬퍼(parse_*, run_analysis)는 단위 테스트 대상.
render_*_step 함수들은 Streamlit 위젯 호출이라 통합 테스트에서만 다룸.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

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
        repo.save(profile)
        st.success(f"저장됨: {slug}.json")
        st.session_state.mode = "generate"
        st.session_state.current_slug = slug
        st.session_state.register_step = 1
        # cleanup
        for k in ["collected_posts", "step2_data", "analyzed_profile", "analysis_done", "source_url"]:
            st.session_state.pop(k, None)
        st.rerun()
```

- [ ] **Step 4: `app.py` 수정 — register_view 연결**

`app.py` 의 `main()` 함수에서 register 분기 교체:

기존:
```python
    if mode == "register":
        st.header("새 브랜드 등록 (Task 11에서 구현)")
        st.info("3-step wizard 가 이 자리에 들어갑니다.")
```

교체:
```python
    if mode == "register":
        from core.claude_client import ClaudeClient
        from ui.register_view import render_register_view
        render_register_view(repo, client_factory=ClaudeClient)
```

- [ ] **Step 5: 테스트 통과 + 수동 smoke**

```powershell
pytest tests/unit/test_register_view.py -v
.\sns_mention\Scripts\Activate.ps1
streamlit run app.py
```

브라우저에서:
- "＋ 새 브랜드 등록" 클릭 → Step 1 화면
- "직접 붙여넣기" 선택 후 텍스트 3개 `---` 로 구분해 입력 → 파싱 → 다음
- Step 2: 브랜드명·금지어 입력 → 분석 시작 (실제 API 호출됨; 키가 있어야 진행 가능)
- Step 3: 분석 결과 표시 → 저장 → 사이드바에 등장

`ANTHROPIC_API_KEY` 가 없으면 Step 3 에서 에러 메시지로 나오는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add ui/register_view.py app.py tests/unit/test_register_view.py
git commit -m "feat(ui): add 3-step brand registration wizard"
```

---

## Task 12: 생성 화면 — Brief 입력 + 3변종 출력

**Files:**
- Create: `ui/generate_view.py`
- Modify: `app.py` (generate_view 연결)
- Create: `tests/unit/test_generate_view.py`

- [ ] **Step 1: 비-UI 로직 테스트 작성**

`tests/unit/test_generate_view.py`:

```python
"""ui/generate_view.py 의 비-UI 헬퍼 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from storage.models import (
    BrandProfile,
    BrandRules,
    Emoji,
    Formatting,
    Hashtag,
    Meta,
    Voice,
)
from ui.generate_view import run_full_generation


def _make_profile() -> BrandProfile:
    return BrandProfile(
        meta=Meta(brand_name="Nike KR", slug="nike-kr", analyzed_at=datetime(2026, 5, 26)),
        voice=Voice(),
        emoji=Emoji(),
        hashtag=Hashtag(),
        formatting=Formatting(),
        brand_rules=BrandRules(forbidden_phrases=["최고의"]),
        example_posts=["예시"],
    )


def test_run_full_generation_calls_generate_then_proofread():
    client = MagicMock()
    client.call_tool.side_effect = [
        {"variants": [
            {"label": "감성", "caption": "원본1", "hashtags": ["#a"]},
            {"label": "정보", "caption": "원본2", "hashtags": ["#b"]},
            {"label": "이벤트 강조", "caption": "원본3", "hashtags": ["#c"]},
        ]},
        {"variants": [
            {"label": "감성", "caption": "교정1", "hashtags": ["#a"]},
            {"label": "정보", "caption": "교정2", "hashtags": ["#b"]},
            {"label": "이벤트 강조", "caption": "교정3", "hashtags": ["#c"]},
        ]},
    ]

    result = run_full_generation(
        client=client,
        profile=_make_profile(),
        brief="6/5~6/15 이벤트",
    )

    assert [v["caption"] for v in result] == ["교정1", "교정2", "교정3"]
    assert client.call_tool.call_count == 2
    assert client.call_tool.call_args_list[0].kwargs["tool_name"] == "emit_variants"
    assert client.call_tool.call_args_list[1].kwargs["tool_name"] == "emit_proofread"


def test_run_full_generation_with_variant_filter_skips_proofread_for_empty():
    client = MagicMock()
    client.call_tool.return_value = {"variants": []}
    result = run_full_generation(
        client=client,
        profile=_make_profile(),
        brief="x",
        variants=["감성"],
    )
    assert result == []
```

- [ ] **Step 2: 실패 확인**

```powershell
pytest tests/unit/test_generate_view.py -v
```

기대: ModuleNotFoundError.

- [ ] **Step 3: `ui/generate_view.py` 구현**

```python
"""카피 생성 화면.

비-UI 헬퍼(run_full_generation)는 generate.write_captions + generate.proofread 를 합쳐
한 번에 3-변종 생성 + 맞춤법 교정을 수행한다.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from core.claude_client import ClaudeClient
from core.generate import proofread, write_captions
from storage.models import BrandProfile
from storage.repo import BrandRepo


# --- 비-UI 헬퍼 ---------------------------------------------------------------

def run_full_generation(
    *,
    client: ClaudeClient,
    profile: BrandProfile,
    brief: str,
    variants: list[str] | None = None,
    extra_instruction: str = "",
) -> list[dict[str, Any]]:
    """1차: 카피 생성 → 2차: 한글 맞춤법·금지어 교정. 교정된 리스트를 반환."""
    generated = write_captions(
        client=client, profile=profile, brief=brief,
        variants=variants, extra_instruction=extra_instruction,
    )
    if not generated:
        return []
    return proofread(client=client, captions=generated, brand_rules=profile.brand_rules)


# --- Streamlit 렌더 ----------------------------------------------------------

def render_generate_view(repo: BrandRepo, client_factory) -> None:
    slug = st.session_state.get("current_slug")
    if not slug:
        st.info("사이드바에서 브랜드를 선택하세요.")
        return

    try:
        profile = repo.load(slug)
    except Exception as e:
        st.error(f"브랜드 로드 실패: {e}")
        return

    st.header(profile.meta.brand_name)
    st.caption(
        f"register: {profile.voice.register} · 평균 길이: {profile.voice.avg_length_chars}자 · "
        f"이모지 평균: {profile.emoji.avg_per_post:.1f}/post"
    )

    with st.expander("브랜드 프로필 / 규칙 보기·편집", expanded=False):
        st.json(profile.model_dump(), expanded=False)
        st.caption("MVP: 인라인 편집은 v2 에서 지원. 지금은 JSON 파일 직접 편집 후 새로고침.")

    brief = st.text_area(
        "Brief (이벤트·신상품 등 핵심 정보)",
        height=140,
        key="brief_input",
        placeholder="6/5~6/15 사전 구매 시 도시락 가방+물병 증정. 한정 수량 200세트.",
    )

    col1, col2, col3 = st.columns(3)
    use_emotional = col1.checkbox("감성", value=True)
    use_factual = col2.checkbox("정보", value=True)
    use_event = col3.checkbox("이벤트 강조", value=True)

    selected: list[str] = []
    if use_emotional:
        selected.append("감성")
    if use_factual:
        selected.append("정보")
    if use_event:
        selected.append("이벤트 강조")

    if st.button("🚀 카피 생성", type="primary", disabled=not (brief.strip() and selected)):
        with st.spinner("Claude 가 카피를 작성하고 맞춤법을 검증합니다..."):
            try:
                results = run_full_generation(
                    client=client_factory(),
                    profile=profile,
                    brief=brief,
                    variants=selected,
                )
            except Exception as e:
                st.error(f"생성 실패: {e}")
                return
        st.session_state.last_results = results
        st.success("✓ 맞춤법 검증 완료")

    results = st.session_state.get("last_results") or []
    for i, variant in enumerate(results):
        with st.container(border=True):
            label = variant.get("label", "")
            st.markdown(f"**변종 {i + 1} [{label}]**")
            st.text_area(
                "caption",
                value=variant.get("caption", ""),
                height=120,
                key=f"caption-{i}",
                label_visibility="collapsed",
            )
            tags = " ".join(variant.get("hashtags", []))
            st.caption(tags or "(해시태그 없음)")

            with st.expander("🔄 이 변종만 다시 생성"):
                extra = st.text_input(
                    "추가 지시 (예: 더 짧게 / 감정 톤 더 살려)",
                    key=f"extra-{i}",
                )
                if st.button("재생성", key=f"regen-{i}"):
                    with st.spinner("재생성 중..."):
                        try:
                            new_variants = run_full_generation(
                                client=client_factory(),
                                profile=profile,
                                brief=brief,
                                variants=[label],
                                extra_instruction=extra,
                            )
                        except Exception as e:
                            st.error(f"재생성 실패: {e}")
                            new_variants = []
                    if new_variants:
                        results[i] = new_variants[0]
                        st.session_state.last_results = results
                        st.rerun()
```

- [ ] **Step 4: `app.py` 수정 — generate_view 연결**

`app.py` 의 generate 분기 교체:

기존:
```python
    elif mode == "generate":
        st.header(f"카피 생성 — {st.session_state.current_slug} (Task 12에서 구현)")
        st.info("Brief 입력 + 3변종 출력이 이 자리에 들어갑니다.")
```

교체:
```python
    elif mode == "generate":
        from core.claude_client import ClaudeClient
        from ui.generate_view import render_generate_view
        render_generate_view(repo, client_factory=ClaudeClient)
```

- [ ] **Step 5: 테스트 통과 + E2E 수동 smoke**

```powershell
pytest tests/unit/test_generate_view.py -v
pytest -v   # 전체 회귀
.\sns_mention\Scripts\Activate.ps1
streamlit run app.py
```

전체 흐름 확인:
1. 새 브랜드 등록 → 사이드바에 등장
2. 사이드바에서 클릭 → 생성 화면 로드
3. Brief 입력 → "카피 생성" → 3변종 출력 + "맞춤법 검증 완료" 표시
4. 출력에 금지어 미포함 / 정확 표기 준수 확인

API 키가 없으면 1·3 단계에서 ClaudeError 가 명확히 표시되는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add ui/generate_view.py app.py tests/unit/test_generate_view.py
git commit -m "feat(ui): add caption generation view with proofread pipeline"
```

---

## Task 13: README + 최종 정리 + 통합 회귀

**Files:**
- Create: `README.md`
- Create: `tests/integration/test_smoke.py`

- [ ] **Step 1: `README.md` 작성**

```markdown
# SNS Mention — 브랜드 맞춤형 인스타그램 캡션 생성기

10년 차 마케터의 워크플로우에 맞춘 1인용 Streamlit 도구.
브랜드 IG 톤을 한 번 학습해두면, Brief 만 넣어 3개 변종(감성·정보·이벤트 강조) 카피를 즉시 생성.

## 빠른 시작

```powershell
# 의존성 설치
uv sync

# 가상환경 활성화
.\sns_mention\Scripts\Activate.ps1

# 환경변수 설정 (.env 파일에)
cp .env.example .env
# .env 의 ANTHROPIC_API_KEY 를 채울 것

# 실행
streamlit run app.py
```

## 명령어

```powershell
pytest                     # 단위 테스트 (Claude 호출 모킹)
pytest -m integration      # 실 Claude 호출 (RUN_INTEGRATION=1 필요, 과금 발생)
ruff check .               # 린트
mypy .                     # 타입 체크
```

## 구조

`docs/superpowers/specs/2026-05-26-sns-mention-design.md` 참조.

- `core/` — Claude 호출 / 수집 / 분석 / 생성 (UI 와 분리)
- `storage/` — JSON 파일 기반 브랜드 프로필 저장소
- `ui/` — Streamlit 사이드바·등록 위저드·생성 화면

## 데이터 위치

브랜드 프로필 JSON: `storage/data/brands/{slug}.json` (gitignore 됨)
```

- [ ] **Step 2: 통합 smoke 테스트 작성**

`tests/integration/test_smoke.py`:

```python
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
```

- [ ] **Step 3: 전체 단위 회귀 + 통합 skip 확인**

```powershell
pytest -v
```

기대:
- 모든 단위 테스트 통과 (Task 2~12 누적)
- integration 테스트는 RUN_INTEGRATION 미설정 → skipped

선택: 실 호출 검증

```powershell
$env:RUN_INTEGRATION = "1"
pytest tests/integration/ -v -m integration
```

- [ ] **Step 4: 린트 + 타입 체크**

```powershell
ruff check .
mypy .
```

문제 발견 시 surgical 수정 (CLAUDE.md 원칙). 광범위 리팩토링 금지.

- [ ] **Step 5: 커밋**

```bash
git add README.md tests/integration/test_smoke.py
git commit -m "docs: add README and Claude integration smoke test"
```

- [ ] **Step 6: 최종 수동 E2E**

`storage/data/brands/` 비운 상태에서 streamlit 앱 새로 띄우고:
1. 브랜드 등록(IG 핸들 또는 paste 10~15개) → 분석 완료까지 확인
2. 사이드바에 새 브랜드 노출 확인
3. 클릭 후 Brief 입력 → 3변종 생성 확인
4. 출력물에 금지어 없는지 / 정확 표기 지키는지 / 한글 맞춤법 자연스러운지

해당 작업의 스크린샷이나 출력 샘플은 PR 본문에 첨부.

---

## Self-Review Notes (이미 수행)

본 계획서는 작성 후 spec 과 대조 검토를 거쳤다.

**Spec coverage 매핑**:
- §1 모듈 구조 → Task 1, 10
- §2 Pydantic 스키마 → Task 2
- §3 워크플로우 (등록/생성) → Task 11, 12
- §4 프롬프트 (분석/생성/교정) → Task 7, 8, 9
- §5 엣지 케이스 (크롤 실패·키 누락·스키마 위반·rate limit) → Task 3 (스키마), 4 (재시도·키), 5/6 (크롤 fallback), 11 (UI 에러)
- §6 테스트 전략 → 매 Task TDD + Task 13 integration
- §7 의존성 → Task 1

**확정 사항**:
- `ClaudeClient` 는 `tool_use` 강제로 JSON 출력. SDK 의 `messages.create` 모킹은 `MagicMock` 으로 응답 객체 합성.
- `BrandRepo.list_with_warnings()` 는 손상된 JSON 파일을 건너뛰고 사이드바에서 ⚠️ 표시.
- `instaloader` 는 best-effort. 모든 예외를 `IngestError` 로 압축해 UI 가 paste fallback 으로 전환 가능.
- 변종 옵션은 체크박스로 1~3개 가변 (스펙 §3-2 self-review 반영).
- 인라인 프로필 편집은 MVP 범위에서 제외 (생성 화면의 expander 는 JSON 보기만 노출, 편집은 v2 노트).
