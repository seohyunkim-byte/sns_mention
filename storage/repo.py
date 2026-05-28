"""브랜드 프로필 JSON 파일 저장소.

`storage/data/brands/{slug}.json` 한 파일 = 한 브랜드.
"""
from __future__ import annotations

import builtins
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
        # \w is Unicode-aware in Python 3 — already covers Hangul.
        s = re.sub(r"[^\w\s\-]", "", s)
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

    def list_with_warnings(self) -> tuple[builtins.list[BrandProfile], builtins.list[str]]:
        profiles: builtins.list[BrandProfile] = []
        warnings: builtins.list[str] = []
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
