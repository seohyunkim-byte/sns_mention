# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Pre-implementation. The repo currently contains only the design spec — no application code yet. The authoritative source for architecture, data model, prompts, and scope is:

[docs/superpowers/specs/2026-05-26-sns-mention-design.md](docs/superpowers/specs/2026-05-26-sns-mention-design.md)

Read it before proposing or writing code. Do not invent structure that contradicts the spec; if the spec needs to change, update it first.

## Parent guidance

The parent `../CLAUDE.md` defines four operating principles (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution). They apply here — don't restate them, do follow them.

## What this project is

Streamlit-based personal tool for a brand marketer. Learns a brand's Instagram voice from existing posts, then generates 3 caption variants (감성 / 정보 / 이벤트 강조) from a marketer-supplied Brief.

Stack: Streamlit + Google Gemini 2.5 Flash + Pydantic + instaloader (best-effort crawler) + dual-mode storage (JSON files locally / Supabase in cloud). Single user, or password-gated small team via Streamlit Cloud.

LLM call shape:
- Brand registration: 1 LLM call (analyze posts → tone profile JSON).
- Caption generation: 2 LLM calls (generate 3 variants → Korean spellcheck/forbidden-word pass).

All LLM calls go through `core/llm_client.py` (single point for retry, logging, mocking). Originally Claude Sonnet 4.6; switched to Gemini 2.5 Flash to leverage the free tier (1,500 req/day). The class name (`LLMClient`) is provider-agnostic so a future swap stays surgical.

## Environment

- **Python**: 3.12+ planned. Current `.venv` (`sns_mention/`) is 3.14.5 — may need downgrade if `instaloader` lacks 3.14 wheels.
- **Package manager**: `uv` (binary at `C:\Users\MADUP\.local\bin\uv.exe`).
- **Venv location**: `./sns_mention/` (named after the project, NOT the conventional `.venv`). Activate with:
  ```powershell
  .\sns_mention\Scripts\Activate.ps1
  ```
- **Secrets**: `.env` with `GEMINI_API_KEY=...` (gitignored). Also accepts `GOOGLE_API_KEY` as alias.

## Commands (once `pyproject.toml` exists per spec §7)

```powershell
uv sync                              # install deps
streamlit run app.py                 # run the app
pytest                               # unit tests (Claude calls mocked)
pytest -m integration                # real Claude calls (opt-in, costs $)
ruff check . ; mypy .                # lint / type-check
```

These commands don't work yet — they're the contract the implementation should satisfy.

## Implementation notes

- Module boundaries are load-bearing: `core/ingest`, `core/analyze`, `core/generate` must not import each other. UI imports only `core/*`, never the other way around.
- Storage is dual-mode: `storage/repo.py` (JSON files, default) and `storage/supabase_repo.py` (Supabase, when `SUPABASE_URL` + `SUPABASE_KEY` both set). The factory lives in `app.py:_make_repo()`. Both classes expose the same method names so callers don't need to branch.
- Brand profile JSON schema is defined in spec §2 — implement it as Pydantic models in `storage/repo.py` and validate on every load. A schema-violating file should surface as a warning in the sidebar, not a crash.
- `brand_rules` (forbidden phrases, must-use names, tone guardrails) is marketer-input, not LLM-extracted. It is supplied to the analyze prompt (to filter `example_posts`) AND to the generate prompt (as hard constraints) AND to the proofread prompt (as final guard).
- Korean spellcheck is a separate LLM call by design — keep it that way. Single-pass generation has been ruled out.

## Conventions specific to this repo

- Design specs live in `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Implementation plans (when written) go alongside.
- `.superpowers/` is brainstorming session artifacts — gitignored, do not commit.
- The venv directory `sns_mention/` is at the repo root and shares a name with the repo; do not delete or move it.
