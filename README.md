# SNS Mention — 브랜드 맞춤형 인스타그램 캡션 생성기

10년 차 마케터의 워크플로우에 맞춘 1인용 Streamlit 도구.
브랜드 IG 톤을 한 번 학습해두면, Brief 만 넣어 3개 변종(감성·정보·이벤트 강조) 카피를 즉시 생성.

## 빠른 시작

이 저장소의 가상환경은 관행적인 `.venv/` 가 아닌 `sns_mention/` 디렉토리입니다.
`uv sync` 가 기본으로 `.venv/` 를 만들지 않도록 환경변수를 먼저 설정하세요.

```powershell
# 가상환경 위치 지정 (PowerShell)
$env:UV_PROJECT_ENVIRONMENT = "sns_mention"

# 의존성 설치 (개발 도구 포함)
uv sync --extra dev

# 가상환경 활성화
.\sns_mention\Scripts\Activate.ps1

# 환경변수 설정 (.env 파일에)
Copy-Item .env.example .env
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

---

## Streamlit Cloud 배포 (팀 공유용)

팀원·친구들과 같이 쓰려면 Streamlit Community Cloud(무료)에 올리는 게 가장 빠릅니다.
이 저장소는 비밀번호 게이트가 미리 들어있어, URL 을 알아도 비밀번호 없이는 진입 불가합니다.

### 사전 준비
- GitHub 계정 + 이 저장소(public OK)
- Anthropic Console 에서 발급한 `ANTHROPIC_API_KEY`
- 팀원들과 공유할 임의의 비밀번호 1개

### 배포 절차

1. https://share.streamlit.io 접속 → "Sign in with GitHub".
2. **"New app"** → 본 저장소(`sns_mention`) + 브랜치(`main` 또는 `feature/sns-mention-mvp`) + 메인 파일 `app.py` 선택 → **Deploy**.
3. 배포 진행 중 우측 상단 메뉴 → **App settings → Secrets** 클릭 후 다음을 붙여넣고 저장:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   APP_PASSWORD = "팀원들과 공유할 비밀번호"
   ```
   (이 두 값은 `.streamlit/secrets.toml.example` 형식 그대로입니다.)
4. 앱이 자동으로 재시작되면 비밀번호 화면이 뜹니다. 팀에 URL + 비밀번호를 공유하면 끝.

### 현재 알려진 제약 (v1)

- **브랜드 프로필 저장은 휘발성입니다.** Streamlit Cloud 무료 티어는 컨테이너가 재시작되면 `storage/data/brands/` 파일이 사라집니다. 즉, 앱 재배포·휴면 후 깨어날 때 등록된 브랜드를 다시 등록해야 합니다.
- **단일 비밀번호 + 공유 라이브러리 모델입니다.** 팀원별 데이터 분리, 사용량 미터링은 v2 작업으로 별도 진행해야 합니다.
- 본격 운영 단계에 들어가면 Supabase·Postgres 등의 영구 저장소를 붙이는 마이그레이션을 권장합니다.

### 로컬에서도 비밀번호 게이트 시험

```powershell
# 1) 시크릿 파일 만들기 (gitignore 됨)
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml   # 값 채우기

# 2) 평소처럼 실행
streamlit run app.py
```

`APP_PASSWORD` 가 비어있거나 누락되면 게이트는 자동 비활성 (= 즉시 진입).
