# 브랜드 맞춤형 인스타그램 멘션 자동 생성 프로그램 — 설계서

- **작성일**: 2026-05-26
- **대상 페르소나**: 10년 차 전문 브랜드 마케터
- **목적**: 특정 브랜드의 인스타그램 톤앤매너를 학습하여, 마케터가 입력한 Brief 를 해당 브랜드 보이스로 자동 카피라이팅

---

## 1. 시스템 구조

### 1-1. 디렉토리 레이아웃

```
sns_mention/
├── app.py                       # Streamlit 진입점 (사이드바 + 메인)
├── core/
│   ├── ingest.py                # IG URL 크롤 → 실패 시 paste fallback
│   ├── analyze.py               # Claude 로 게시물 → 톤 프로필 추출
│   ├── generate.py              # 프로필 + Brief → 3개 카피 생성 + 맞춤법 교정
│   └── claude_client.py         # Anthropic SDK 래퍼 (재시도, 모킹 가능)
├── storage/
│   ├── repo.py                  # JSON 파일 CRUD
│   └── data/brands/*.json       # 브랜드별 프로필 파일
├── ui/
│   ├── sidebar.py               # 브랜드 목록 + 새 등록 버튼
│   ├── register_view.py         # 3-step 신규 브랜드 등록 위저드
│   └── generate_view.py         # 카피 생성 화면
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── .env                         # ANTHROPIC_API_KEY (gitignore)
├── pyproject.toml               # uv 의존성 관리
└── README.md
```

### 1-2. 설계 원칙

- **단일 책임 모듈**: `ingest` / `analyze` / `generate` 는 서로 모름. 각자 입출력 계약만 가짐.
- **UI 와 비즈니스 로직 분리**: `ui/*` 는 `core/*` 만 호출. 비즈니스 로직 UI 에 섞지 않음.
- **LLM 호출 단일 진입점**: 모든 Claude 호출은 `core/claude_client.py` 만 통과. 재시도·로깅·모킹을 한 곳에서.
- **YAGNI**: DB·인증·다중 사용자·이미지 생성 등은 범위 외.

### 1-3. 데이터 흐름

```
[브랜드 등록]
  IG URL 입력 ──→ ingest.crawl() ──┬─ 성공 → 게시물 텍스트 리스트
                                    └─ 실패 → 마케터 paste
                                              ↓
              analyze.extract_profile()    (Claude 호출 1)
                                              ↓
              {프로필 JSON + 대표 예제 3~5}  ──→ repo.save()

[카피 생성]
  사이드바 브랜드 클릭 → 프로필 로드
  Brief 입력 → generate.write_captions()    (Claude 호출 1)
              → generate.proofread()        (Claude 호출 2)
              ↓
  3개 카피 변종 (감성 / 정보 / 이벤트 강조)
```

---

## 2. 데이터 모델 — 브랜드 프로필 JSON 스키마

`storage/data/brands/{slug}.json` 한 파일 = 한 브랜드. Pydantic 으로 검증.

```jsonc
{
  "meta": {
    "brand_name": "나이키 KR",
    "slug": "nike-kr",
    "ig_handle": "@nike_kr",
    "source_url": "https://...",
    "analyzed_at": "2026-05-26T10:00:00",
    "post_count": 18,
    "model_version": "claude-sonnet-4-6"
  },
  "voice": {
    "register": "casual",
    "address_form": "반말+여러분",
    "sentence_endings": ["~해요", "~죠", "~합니다"],
    "avg_length_chars": 87,
    "humor_level": 2,
    "emotion_level": 4,
    "signature_phrases": ["Just Do It", "한계를 넘어"]
  },
  "emoji": {
    "avg_per_post": 0.4,
    "top": ["🔥", "💪", "⚡"],
    "placement": "end_of_sentence"
  },
  "hashtag": {
    "avg_count": 6,
    "signature": ["#나이키", "#JustDoIt"],
    "common": ["#운동", "#러닝", "#스포츠"]
  },
  "formatting": {
    "line_breaks": "frequent",
    "uses_caps": false,
    "uses_bullet_markers": false
  },
  "topics": ["러닝", "스포츠 동기부여"],

  "brand_rules": {
    "must_use_names": [
      { "term": "Nike",       "note": "영문, 대문자 N + 소문자 ike" },
      { "term": "에어 조던",   "note": "띄어쓰기 필수, '에어조던' 금지" },
      { "term": "Just Do It", "note": "구두점 없음, 단어 사이 공백 1칸" }
    ],
    "forbidden_phrases": ["최고의", "유일한", "1등", "아디다스", "단언컨대"],
    "tone_guardrails": ["정치/종교 발언 금지", "이모지 5개 초과 금지"]
  },

  "example_posts": [
    "오늘은 어제보다 1km 더. 🔥 ...",
    "한계를 넘는 순간, 새로운 자신을 만나죠. ..."
  ]
}
```

**필드 분리 근거**:

- `voice` 가 핵심 — LLM 지시 시 임팩트 가장 큼.
- `example_posts` 3~5 개가 in-context learning 의 결정 재료.
- `brand_rules` 는 등록 시 마케터 직접 입력 (분석으로 자동 추출 ❌).
- `model_version` 은 향후 Claude 업그레이드 시 재분석 트리거 용.

---

## 3. 핵심 워크플로우

### 3-1. 브랜드 등록 (3-step Wizard, `st.session_state` 관리)

**Step 1 — 데이터 수집**
- IG URL 입력 → "크롤 시도" 버튼
- 성공: 가져온 게시물 N 개 미리보기 (편집 가능)
- 실패: 자동으로 paste UI 전환 (실패 사유 표시). textarea 에 `---` 구분자로 10~30 개 paste
- "다음" 버튼

**Step 2 — 브랜드 규칙 입력 (분석 전)**
- 브랜드명 (필수)
- 정확 표기 (브랜드명/제품명, 동적 추가)
- 금지 표현 (한 줄에 하나)
- 톤 가드레일 (자유 텍스트, 선택)
- "분석 시작" 버튼 → Claude 호출 (10~30 초)
- **brand_rules 를 분석 전에 받는 이유**: 분석 시 Claude 가 "금지어 들어간 게시물은 example_posts 에서 제외"하도록 지시 가능.

**Step 3 — 분석 결과 미리보기 + 편집**
- 추출된 voice / emoji / hashtag 표시
- 모든 필드 인라인 편집 가능 (Claude 100% 가정 금지)
- 대표 예제 5 개 체크박스로 제외 가능
- "저장" 버튼 → JSON 저장 → 사이드바 갱신 → 카피 생성 화면 이동

### 3-2. 카피 생성

```
[사이드바] 브랜드 클릭
    ↓
[메인]
  ▸ 브랜드 카드 (이름 / 톤 요약 / 평균 길이)
  ▸ "프로필 보기/편집" 토글 (접힘 기본)

  Brief (multi-line, 500 자 권장)
  ┌──────────────────────────────────┐
  │ 6/5~6/15 사전 구매 시 도시락 가방+ │
  │ 물병 증정. 한정 수량 200세트.       │
  └──────────────────────────────────┘

  [옵션]
  □ 변종 방향: ☑ 감성 ☑ 정보 ☑ 이벤트 강조
  □ 길이: ○ 짧게  ◉ 보통  ○ 길게

  [🚀 3개 카피 생성]
    ↓
  Claude 호출 1 (생성) → Claude 호출 2 (맞춤법 교정)
    ↓
  변종 1 [감성]
  ┌────────────────────────────┐
  │ (캡션 본문)                  │
  │ #해시태그 #해시태그           │
  └────────────────────────────┘
  [📋 복사] [🔄 이 변종만 다시] [✏️ 직접 편집]

  변종 2 [정보] ...
  변종 3 [이벤트 강조] ...
  ✓ 맞춤법 검증 완료
```

**결정**:
- 변종 방향 3 개 고정 — 마케팅 카피의 표준 3 축 (감성 / 정보 / 이벤트 강조).
- 변종 옵션 체크박스: 체크된 변종만 생성 (1~3 개). 기본 3 개 모두 체크.
- 단일 재생성: 해당 변종 카드 옆 보조 지시 입력창 ("더 짧게", "감정 톤 더 살려"). 입력값은 4-2 프롬프트의 Brief 뒤에 `=== 추가 지시 (이 변종만) ===` 으로 주입. 빈 값이면 동일 프롬프트로 재호출.
- `프로필 보기/편집` 토글: voice / emoji / hashtag / formatting / brand_rules 까지 모두 인라인 편집. 저장 시 JSON 파일 갱신 (재분석 X).

---

## 4. LLM 프롬프트 설계

### 4-1. 톤 프로필 추출 (`analyze.py`)

```
[System]
당신은 10년 차 브랜드 톤앤매너 분석 전문가다.
주어진 인스타그램 게시물들을 읽고 브랜드의 일관된 보이스를 JSON 으로 추출하라.

규칙:
- 추측 금지. 게시물에서 확인되는 패턴만 기록.
- 빈도가 낮은 표현(1~2회)은 시그니처로 보지 말 것.
- 금지어 목록과 겹치는 표현은 example_posts 에서 제외하라.

[User]
브랜드명: {brand_name}
금지 표현: {forbidden_phrases}
게시물 ({N}개):
---
{post_1}
---
{post_2}
...

출력 (반드시 이 JSON 만):
{ "voice": {...}, "emoji": {...}, "hashtag": {...},
  "formatting": {...}, "topics": [...], "example_posts": [...] }
```

- Anthropic SDK `tool_use` 로 JSON 스키마 강제
- 스키마 위반 시 1회 재시도, 그래도 실패하면 raw 응답을 마케터에게 표시하고 수동 입력

### 4-2. 카피 생성 (`generate.py`, 1차 호출)

```
[System]
당신은 {brand_name} 의 인스타그램 카피라이터다.
아래 브랜드 프로필을 완벽히 학습하여, Brief 를 카피 3 변종으로 작성하라.

[중요 제약 — 위반 시 실격]
1. 다음 표현은 절대 사용 금지: {forbidden_phrases}
2. 다음 명칭은 정확히 이 표기로만: {must_use_names_with_notes}
3. 국립국어원 표준 맞춤법·띄어쓰기 엄격 준수.
4. Brief 에 없는 사실(가격·기간·수량) 임의 생성 금지.
5. 변종별 차별점:
   - 변종 1 (감성): 감정·스토리·공감 중심
   - 변종 2 (정보): 혜택·스펙·이유 중심
   - 변종 3 (이벤트 강조): 한정성·CTA·기간 강조

[User]
=== 브랜드 프로필 ===
{voice / emoji / hashtag / formatting}

=== 시그니처 표현 (자연스럽게 1~2개 활용) ===
{signature_phrases}

=== 대표 게시물 (이 톤으로 써라) ===
{example_posts}

=== 톤 가드레일 ===
{tone_guardrails}

=== Brief ===
{brief}

=== 출력 ===
JSON: { "variants": [
  { "label": "감성",       "caption": "...", "hashtags": [...] },
  { "label": "정보",       "caption": "...", "hashtags": [...] },
  { "label": "이벤트 강조", "caption": "...", "hashtags": [...] }
]}
```

### 4-3. 맞춤법·금지어 검증 (`generate.py`, 2차 호출)

```
[System]
당신은 한국어 교정 전문가다. 아래 카피 3 개를 검토하여 다음만 수정하라:
1. 맞춤법·띄어쓰기 오류 (국립국어원 기준)
2. 자주 틀리는 케이스: 되/돼, 안/않, 률/율, 어색한 외래어 표기
3. 금지 표현 {forbidden_phrases} 포함 시 자연스럽게 치환
4. 정확 표기 {must_use_names} 위반 시 교정

수정 없으면 원문 그대로 반환. 의역·재창작·톤 변경 금지. 오직 교정만.

[User]
{variant_1.caption}
---
{variant_2.caption}
---
{variant_3.caption}

[출력] 같은 JSON 구조로 교정된 caption 만.
```

### 4-4. 모델 선택

| 호출 | 모델 | 이유 |
|------|------|------|
| 톤 분석 | claude-sonnet-4-6 | 30개 게시물 패턴 추출, 가성비 |
| 카피 생성 | claude-sonnet-4-6 | 한국어 카피 품질 충분 |
| 맞춤법 교정 | claude-sonnet-4-6 | 짧은 입력, 정확도 중시 |

품질 부족 시 `claude_client` 의 모델 ID 만 교체해 Opus 로 업그레이드 가능 (코드 변경 0).

---

## 5. 에러 처리·엣지 케이스

| 상황 | 처리 |
|------|------|
| IG 크롤 실패 (rate limit / 비공개 / 로그인 요구) | 사유 표시 + 자동 paste UI 전환 |
| 수집 게시물 < 5 | 품질 저하 경고. 진행/중단 마케터 선택 |
| 수집 게시물 > 50 | 비용 안내 후 최신 30 개만 사용 |
| Claude JSON 깨짐 | `tool_use` 강제 + 1회 재시도. 2회 실패 시 raw 응답 + 수동 입력 옵션 |
| API 키 미설정 | 시작 시 `.env` 체크. 누락 시 설정 안내 화면 |
| Claude rate limit / 네트워크 오류 | tenacity exponential backoff 3회. 실패 시 재시도 버튼 |
| brand_name 중복 | slug 충돌 시 "(2)" suffix 또는 덮어쓰기/취소 다이얼로그 |
| Brief 너무 짧음 (<10 자) | 경고 표시, 강제 차단은 안 함 |
| Brief 너무 김 (>1000 자) | 부드러운 경고 |
| 금지어가 example_posts 에 발견 | 분석 단계 자동 필터. 통과 시 미리보기 ⚠️ 표시 |
| JSON 파일 손상 / 스키마 위반 | pydantic 검증 실패 → 사이드바 ⚠️ + 백업 후 마이그레이션 시도 |
| 생성된 카피가 금지어 포함 | 4-3 단계 치환. 잔존 시 UI ⚠️ + 강조 |

---

## 6. 테스트 전략

```
tests/
├── unit/
│   ├── test_repo.py             # JSON CRUD, slug 충돌, 스키마 검증
│   ├── test_ingest.py           # paste 파싱 (구분자), URL 파싱
│   ├── test_analyze.py          # 프롬프트 빌더 + Mock Claude
│   ├── test_generate.py         # 프롬프트 빌더 + Mock Claude
│   └── test_brand_rules.py      # 금지어 검출, 정확 표기 검증
├── fixtures/
│   ├── posts/nike_kr.txt
│   └── profiles/sample.json
└── integration/                 # RUN_INTEGRATION=1 일 때만
    ├── test_real_analyze.py     # 실제 Claude 호출 1회
    └── test_real_generate.py    # 실제 Claude 호출 1회
```

**원칙**:
- Unit 은 `claude_client` 모킹 (`MagicMock` 으로 결정적 응답).
- Integration 은 옵션 (CI 비용·키 노출). `pytest -m integration` 으로 분리.
- UI 테스트는 최소. 핵심 로직은 `core/` 에서 검증.
- 버그 = 회귀 테스트 1개 추가 ("Write a test that reproduces it, then make it pass").

---

## 7. 의존성·환경

```toml
# pyproject.toml (uv 관리)
[project]
name = "sns_mention"
requires-python = ">=3.12"
dependencies = [
    "streamlit>=1.36",
    "anthropic>=0.40",
    "pydantic>=2.7",
    "instaloader>=4.13",      # IG 크롤 best-effort
    "python-dotenv>=1.0",
    "tenacity>=8.5",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock", "ruff", "mypy"]
```

**Python 버전 메모**: 현재 venv 는 3.14. instaloader 등 3.14 wheel 미지원 시 3.12 로 다운그레이드.

**환경변수** (`.env`):
```
ANTHROPIC_API_KEY=sk-ant-...
RUN_INTEGRATION=0
```

---

## 8. 범위 외 (Out of Scope)

YAGNI 원칙에 따라 본 MVP 에서 다루지 않음:

- 이미지/릴스 생성
- 게시물 자동 발행 (IG 업로드 API)
- 다중 사용자 인증·권한
- 클라우드 배포·SaaS 화
- 성과 분석 (도달·반응·전환률)
- A/B 테스트 자동화
- 다국어 번역
- 음성/영상 자막

이들 중 후속으로 필요해질 가능성 — 별도 spec 으로 분리.

---

## 9. 전체 결정 요약

| 항목 | 결정 |
|------|------|
| UI | Streamlit, 사이드바 + 메인 1 페이지 |
| 데이터 수집 | IG 크롤 → 실패 시 paste fallback |
| LLM | Claude Sonnet 4.6. 브랜드 등록 시 1회(분석), 카피 생성 시 2회(생성 + 교정) |
| 저장소 | JSON 파일 (`storage/data/brands/`) |
| 톤 학습 | 구조화 프로필 + 대표 게시물 3~5개 하이브리드 |
| 출력 | 3개 변종 (감성 / 정보 / 이벤트 강조) |
| 브랜드 규칙 | 정확 표기 / 금지 표현 / 톤 가드레일 (마케터 입력) |
| 품질 보증 | 2단계 LLM (생성 → 한글 맞춤법 교정) |
| 테스트 | pytest, Claude 모킹 기본, 실호출은 옵션 |
