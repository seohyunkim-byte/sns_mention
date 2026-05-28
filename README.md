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
