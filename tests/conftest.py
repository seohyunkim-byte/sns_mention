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
