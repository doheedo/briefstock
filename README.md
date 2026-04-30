# Briefstock

Briefstock은 매일 아침 관심 종목 요약을 텔레그램으로 보내주는 자동 브리핑 도구입니다.

- 입력: 관심 종목 목록(`config/watchlist.yaml`)
- 수집: 가격, 뉴스, 공시(SEC/DART), 보조 정보
- 출력: 텔레그램 메시지 + HTML 리포트 첨부

---

## 이 프로젝트로 할 수 있는 것

- 매일 1번 자동으로 브리프 받기
- 종목별 1년 차트와 핵심 이벤트를 한 파일(HTML)로 보기
- LLM 요약을 켜거나 끄기
- GitHub Actions로 운영(권장), 서버 수동 실행도 가능

---

## 5분 시작 가이드 (Windows)

### 1) 설치

```bash
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

### 2) 환경 변수 파일 만들기

- `.env.example`를 복사해서 `.env`를 만듭니다.
- 먼저 아래 2개만 넣으면 텔레그램 발송 테스트가 가능합니다.

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### 3) 관심 종목 설정

`config/watchlist.yaml`에서 종목을 설정합니다.  
필수 값은 아래 6개입니다.

- `ticker`: 티커 (예: AAPL)
- `name`: 회사명
- `market`: 시장 (예: US, KR)
- `thesis`: 투자 메모
- `keywords`: 뉴스 매칭 키워드 목록
- `source_priority`: 우선 수집 순서

### 4) 한 번 실행해보기

```bash
.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-30 --skip-telegram
```

### 5) 생성 파일 확인

- `reports/html/YYYY-MM-DD.html`
- `reports/json/YYYY-MM-DD.json`
- `reports/charts/YYYY-MM-DD/{ticker}.png`

---

## 텔레그램 연결

1. BotFather에서 봇을 만듭니다.
2. 봇에게 메시지를 1회 보냅니다.
3. Chat ID를 확인해 `.env`에 넣습니다.

### BotFather 사용법 (처음 하는 분용)

1. 텔레그램 앱에서 `@BotFather`를 검색해 채팅을 엽니다.
2. `/newbot` 입력
3. 안내에 따라
   - 봇 표시 이름(예: `My Briefing Bot`)
   - 봇 아이디(반드시 `bot`으로 끝남, 예: `my_briefing_alarm_bot`)
     를 입력합니다.
4. 생성이 끝나면 BotFather가 토큰을 줍니다. 이 값을 `.env`의 `TELEGRAM_BOT_TOKEN`에 넣습니다.

### Chat ID 확인 방법

가장 쉬운 방법:

1. 방금 만든 봇과의 채팅방에 들어가서 아무 메시지나 1번 보냅니다(예: `hello`).
2. 브라우저에서 아래 주소를 엽니다.  
   `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates`
3. 응답 JSON에서 `chat` → `id` 값을 찾습니다.
4. 이 숫자를 `.env`의 `TELEGRAM_CHAT_ID`에 넣습니다.

예시:

```text
https://api.telegram.org/bot123456789:ABCDEF.../getUpdates
```

테스트 메시지:

```bash
.\.venv\Scripts\python.exe scripts\send_telegram_test.py
```

---

## 환경 변수 쉽게 설명

아래는 자주 쓰는 항목만 먼저 이해하면 됩니다.

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
NEWS_API_BASE_URL=
NEWS_API_KEY=
SEC_USER_AGENT=DailyStockBriefing/0.1 contact@example.com
DART_API_KEY=
LLM_PROVIDER=auto
GROQ_API_KEY=
NVIDIA_API_KEY=
NVIDIA_LLM_MODEL=deepseek-ai/deepseek-v4-pro
```

### LLM 선택 순서 (중요)

`LLM_PROVIDER=auto`일 때:

1. `NVIDIA_API_KEY`가 있으면 **NVIDIA 우선 사용**
2. NVIDIA 키가 없고 `GROQ_API_KEY`가 있으면 Groq 사용
3. 둘 다 없으면 LLM 없이 기본 요약 문구 사용

즉, 현재 기본 동작은 **NVIDIA 우선**입니다.

### 추천 세팅

- NVIDIA만 사용: `NVIDIA_API_KEY`만 넣기 (`LLM_PROVIDER=auto`)
- Groq만 사용: `NVIDIA_API_KEY` 비우고 `GROQ_API_KEY`만 넣기
- LLM 완전 비활성: `LLM_PROVIDER=none`

---

## 자동 실행 운영 (권장)

### GitHub Actions (권장 운영 방식)

- 매일 `23:00 UTC` = 한국 `08:00 KST` 자동 실행
- 텔레그램 메시지 + HTML 첨부 발송

필요한 GitHub Secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NEWS_API_BASE_URL`
- `NEWS_API_KEY`
- `SEC_USER_AGENT`
- `DART_API_KEY`
- `NVIDIA_API_KEY`
- `NVIDIA_LLM_MODEL`
- `GROQ_API_KEY`

---

## Oracle 서버 사용 (선택)

GitHub Actions만으로도 운영 가능합니다.  
서버는 보조 운영/수동 실행 용도로만 쓰는 것을 권장합니다.

서버 수동 실행:

```bash
bash deploy/oracle/run_daily_briefing.sh
```

---

## 리포트에 들어가는 내용

- 종목별 현재가/등락률
- 5일, 1개월, 1년 수익률
- 벤치마크 대비 상대 수익률
- RSI(14)
- 핵심 뉴스/공시 기반 이벤트
- 종목별 참고 링크(SEC/DART/Yellowbrick 등)

참고: HTML은 텔레그램 전송 안정성을 위해 차트를 파일 내부(Base64)로 포함합니다.

---

## 문제 생겼을 때 빠른 점검

1. `.env`의 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 값 확인
2. 로컬 테스트 실행:

```bash
.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-30 --skip-telegram
```

3. 로그 확인: `logs/briefstock.log`
4. 결과 파일 확인: `reports/html/`, `reports/json/`

---

## 테스트 (개발용)

```bash
.\.venv\Scripts\python.exe -m pytest tests -v
```
