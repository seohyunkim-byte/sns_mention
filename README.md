# SNS Mention — 브랜드 맞춤형 인스타그램 캡션 생성기

10년 차 마케터의 워크플로우에 맞춘 1인용 Streamlit 도구.
브랜드 IG 톤을 한 번 학습해두면, Brief 만 넣어 3개 변종(감성·정보·이벤트 강조) 카피를 즉시 생성.

**LLM**: Google Gemini 2.5 Flash Lite (현재 무료 등급에서 안정적으로 호출 가능한 유일한 옵션). 분석·생성·맞춤법 교정 모두 동일 모델. 환경변수 `GEMINI_MODEL` 로 다른 모델 지정 가능하지만 대부분 무료 한도가 0/매우 낮음. 더 좋은 품질이 필요하면 Google AI Studio 결제(매우 저렴) 후 `gemini-2.5-flash` 사용 권장.

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
# .env 의 GEMINI_API_KEY 를 채울 것 (https://aistudio.google.com 에서 발급)

# 실행
streamlit run app.py
```

## 명령어

```powershell
pytest                     # 단위 테스트 (Gemini 호출 모킹)
pytest -m integration      # 실 Gemini 호출 (RUN_INTEGRATION=1 필요, 무료 등급 한도 내)
ruff check .               # 린트
mypy core storage ui app.py  # 타입 체크
```

## 구조

`docs/superpowers/specs/2026-05-26-sns-mention-design.md` 참조.

- `core/` — LLM 호출 / 수집 / 분석 / 생성 (UI 와 분리)
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
- Google AI Studio 에서 발급한 `GEMINI_API_KEY` — https://aistudio.google.com → "Get API key"
  - 무료 등급은 **모델별로** 다르며, 자주 변경됩니다. 본 앱 기본 모델 `gemini-2.5-flash-lite` 기준 일 1,000회 수준 (정확한 한도는 https://ai.google.dev/gemini-api/docs/rate-limits 에서 확인)
  - `gemini-2.0-flash` 와 `gemini-2.5-flash` 는 현재 free tier 한도가 0 또는 매우 낮음. 본 앱은 lite 를 기본값으로 사용
- 팀원들과 공유할 임의의 비밀번호 1개

### 배포 절차

1. https://share.streamlit.io 접속 → "Sign in with GitHub".
2. **"New app"** → 본 저장소(`sns_mention`) + 브랜치(`main` 또는 `feature/sns-mention-mvp`) + 메인 파일 `app.py` 선택 → **Deploy**.
3. 배포 진행 중 우측 상단 메뉴 → **App settings → Secrets** 클릭 후 다음을 붙여넣고 저장:
   ```toml
   GEMINI_API_KEY = "your-google-ai-studio-key"
   APP_PASSWORD = "팀원들과 공유할 비밀번호"
   # GEMINI_MODEL = "gemini-2.5-flash-lite"   # 기본값. 다른 모델 쓰려면 주석 해제 + 값 변경
   ```
   (이 값들은 `.streamlit/secrets.toml.example` 형식 그대로입니다.)
4. 앱이 자동으로 재시작되면 비밀번호 화면이 뜹니다. 팀에 URL + 비밀번호를 공유하면 끝.

### 현재 알려진 제약 (v1)

- **브랜드 프로필 저장은 휘발성입니다.** Streamlit Cloud 무료 티어는 컨테이너가 재시작되면 `storage/data/brands/` 파일이 사라집니다. 즉, 앱 재배포·휴면 후 깨어날 때 등록된 브랜드를 다시 등록해야 합니다.
- **단일 비밀번호 + 공유 라이브러리 모델입니다.** 팀원별 데이터 분리, 사용량 미터링은 v2 작업으로 별도 진행해야 합니다.
- **Gemini 무료 등급 한도는 모델·시점에 따라 변동**. 현재 기본 `gemini-2.5-flash-lite` 기준 분당·일별 호출 제한 존재. 한 번의 카피 생성 = 분석 1회 (등록 시 1번) + 생성 2회 = 합 3회. 한도 초과 시 429 에러가 뜨고 일정 시간 후 자동 복구 (요금 청구 X, 카드 등록 안 했다면).

---

## 영구 저장소 (Supabase 무료)

Streamlit Cloud 무료 티어는 컨테이너 재시작 시 파일 시스템이 초기화돼 등록된 브랜드 프로필이 사라집니다. 데이터를 영구 보관하려면 Supabase 무료 프로젝트를 연결하세요. 두 환경변수(`SUPABASE_URL`, `SUPABASE_KEY`)가 모두 채워지면 자동으로 Supabase 모드로 동작하고, 비어 있으면 기존처럼 로컬 JSON 파일을 사용합니다.

### 세팅 (한 번만)

1. https://supabase.com 회원가입 → 새 프로젝트 생성 (Region 은 가까운 지역 아무거나, 비밀번호 임의 입력)
2. 프로젝트 대시보드 좌측 **SQL Editor** → "New query" → 아래 SQL 붙여넣고 "Run":
   ```sql
   create table brand_profiles (
     slug text primary key,
     data jsonb not null,
     updated_at timestamptz not null default now()
   );
   ```
3. 좌측 **Settings → API** 메뉴 → 다음 두 값 복사:
   - **Project URL** (`https://xxxx.supabase.co` 형식)
   - **anon public** key (`eyJh...` 로 시작하는 긴 문자열, 절대 `service_role` 키 X)
4. Streamlit Cloud → Settings → Secrets 에 다음 두 줄 추가:
   ```toml
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_KEY = "eyJh..."
   ```
5. **Save** → 앱 자동 재배포 → 그 이후 등록하는 브랜드 데이터는 Supabase에 영구 저장됨

### 동작 모드 확인

- 두 환경변수 모두 비어있음 → 로컬 JSON 파일 (휘발성, 개발용)
- 두 환경변수 모두 채워짐 → Supabase (영구)
- 하나만 채워져 있음 → 안전하게 로컬 모드로 폴백
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
