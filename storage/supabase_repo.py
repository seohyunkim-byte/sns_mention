"""Supabase 기반 영구 브랜드 프로필 저장소.

Streamlit Cloud 휘발성 파일 시스템 문제를 우회한다. 환경변수
`SUPABASE_URL` 과 `SUPABASE_KEY` (anon public key) 가 둘 다 설정된 경우에만 사용.

테이블 스키마 — Supabase 대시보드의 SQL Editor 에서 1회 실행:

    create table brand_profiles (
      slug text primary key,
      data jsonb not null,
      updated_at timestamptz not null default now()
    );

`storage.repo.BrandRepo` 와 동일한 메서드 시그니처를 노출하므로
호출부(`ui/*`, `app.py`)는 둘 중 어느 구현이 주입되든 변경 없이 작동한다.
"""
from __future__ import annotations

import builtins
from typing import Any

from pydantic import ValidationError
from supabase import Client, create_client

from .models import BrandProfile
from .repo import BrandRepo, RepoError

TABLE_NAME = "brand_profiles"


class SupabaseBrandRepo:
    """BrandRepo 와 동일 인터페이스. Supabase 의 jsonb 컬럼에 프로필 JSON 직접 저장."""

    def __init__(self, *, url: str, key: str, client: Client | None = None):
        # client 인자는 테스트에서 mock 주입용. 실제 사용 시엔 url+key 만으로 충분.
        self._client: Client = client or create_client(url, key)

    # slugify 는 BrandRepo 와 동일 알고리즘 — 한 곳에서만 관리.
    @staticmethod
    def slugify(name: str) -> str:
        return BrandRepo.slugify(name)

    def exists(self, slug: str) -> bool:
        result = (
            self._client.table(TABLE_NAME)
            .select("slug")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        return bool(result.data)

    def unique_slug(self, base_slug: str) -> str:
        if not self.exists(base_slug):
            return base_slug
        n = 2
        while self.exists(f"{base_slug}-{n}"):
            n += 1
        return f"{base_slug}-{n}"

    def save(self, profile: BrandProfile) -> str:
        """Upsert — 동일 slug 가 있으면 덮어쓴다. 반환값은 slug."""
        data: dict[str, Any] = profile.model_dump(mode="json")
        self._client.table(TABLE_NAME).upsert(
            {"slug": profile.meta.slug, "data": data}
        ).execute()
        return profile.meta.slug

    def load(self, slug: str) -> BrandProfile:
        result = (
            self._client.table(TABLE_NAME)
            .select("data")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise RepoError(f"brand '{slug}' not found")
        try:
            return BrandProfile.model_validate(result.data[0]["data"])
        except ValidationError as e:
            raise RepoError(f"schema violation in '{slug}': {e}") from e
        except (KeyError, TypeError) as e:
            raise RepoError(f"invalid data shape in '{slug}': {e}") from e

    def list(self) -> builtins.list[BrandProfile]:
        profiles, _ = self.list_with_warnings()
        return profiles

    def list_with_warnings(self) -> tuple[builtins.list[BrandProfile], builtins.list[str]]:
        result = self._client.table(TABLE_NAME).select("slug, data").execute()
        profiles: builtins.list[BrandProfile] = []
        warnings: builtins.list[str] = []
        for row in result.data or []:
            slug = row.get("slug", "?")
            try:
                profiles.append(BrandProfile.model_validate(row["data"]))
            except (ValidationError, KeyError, TypeError) as e:
                warnings.append(f"{slug}: {e}")
        profiles.sort(key=lambda x: x.meta.brand_name.lower())
        return profiles, warnings

    def delete(self, slug: str) -> bool:
        if not self.exists(slug):
            return False
        self._client.table(TABLE_NAME).delete().eq("slug", slug).execute()
        return True
