# Briefstock

Briefstock은 사용자가 설정한 관심 종목(Watchlist)에 대한 일일 주식 브리핑을 제공하는 자동화 파이프라인입니다. 

이 파이프라인은 매일 주가 스냅샷, 뉴스, SEC/DART 공시 자료를 수집하고 기업 이벤트를 분류하여 JSON 및 HTML 형태의 리포트를 작성합니다. 최종적으로 작성된 리포트는 요약된 텍스트와 함께 텔레그램(Telegram) 메시지로 발송됩니다.

주가 데이터 레이어는 단순 현재가 외에도 5일(5D), 1개월(1M), 1년(1Y) 수익률과 벤치마크 대비 상대 수익률, RSI(14) 지표를 추적합니다. 또한 구글 이미지 검색 크롤링에 의존하지 않고, `yfinance` 데이터와 `matplotlib`을 사용하여 1년 주가 추이 PNG 차트를 직접 생성합니다.

## ⚙️ 설정 및 설치 (Setup)

가상환경을 생성하고 의존성 패키지를 설치합니다.

```bash
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

`.env.example` 파일을 복사하여 `.env` 파일을 생성한 뒤, 사용하고자 하는 프로바이더의 API 키만 채워 넣습니다.

## 📝 관심 종목 설정 (Configuration)

`config/watchlist.yaml` 파일을 수정하여 브리핑을 받을 종목을 설정합니다.

각 항목별 필수 필드는 다음과 같습니다:
* `ticker` (티커)
* `name` (기업명)
* `market` (시장)
* `thesis` (투자 아이디어)
* `keywords` (관련 키워드)
* `source_priority` (출처 우선순위)

선택적 필드: `group`, `aliases`, `exclude_keywords`, `thesis_questions`, `red_flags`, `positive_signals`, `min_keyword_matches`

## 💻 로컬 실행 (Local Run)

아래 명령어를 통해 로컬 환경에서 파이프라인을 실행할 수 있습니다.

```bash
.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-25 --skip-telegram
```

그룹 인자를 지정하여 실행할 수도 있습니다 (통합 발송 모드에서는 무시됨):

```bash
.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-25 --group data_info --skip-telegram
```

**출력물 (Outputs):**
* `reports/html/YYYY-MM-DD.html`
* `reports/json/YYYY-MM-DD.json`
* `reports/charts/YYYY-MM-DD/{ticker}.png`

> 참고: 하위 호환성을 위해 `--group` 인자를 지원하지만, 현재 파이프라인은 실행 시마다 단일 통합 결과물만 출력하도록 설계되어 있어 실제 동작에서는 무시됩니다.

## 📊 리포트 구성 (Reports)

HTML 리포트에는 관심 종목 전체 슬라이스와 각 종목별 1년 차트가 포함됩니다. 텔레그램의 `sendDocument` 기능을 통해 독립적인 리포트가 전송될 수 있도록 차트 이미지는 Base64 데이터 URI 형태로 HTML 파일 내에 직접 임베딩됩니다. 텔레그램 메시지 본문은 수치 요약 위주로 간략하게 유지되며, 개별 차트 이미지를 일일이 보내는 대신 HTML 리포트 파일을 첨부하여 발송합니다.

**가격 섹션 포함 내역:**
* 현재가 및 1일 변동률
* 5D, 1M, 1Y 수익률
* 벤치마크 1년 수익률 (해외 티커: `^GSPC`, 국내 티커: `^KS200` 적용)
* 선택된 벤치마크 대비 1년 상대 수익률
* RSI(14)

지분 변동 공시(Form 3, 4, 5, 144 등)는 기본적으로 간략하게 처리됩니다. 리포트는 관련 뉴스를 주요 요약 출처로 취급하며, 관련 뉴스가 없는 경우에 한해 공시 원문을 펼쳐 보여주지 않고 낮은 우선순위의 내부자/지분 공시로 표시합니다.

## 📱 텔레그램 연동 (Telegram)

BotFather를 통해 봇을 생성하고, 봇에게 메시지를 보내 Chat ID를 확인합니다. `.env` 파일에 다음을 설정합니다:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

테스트 메시지 발송:

```bash
.\.venv\Scripts\python.exe scripts\send_telegram_test.py
```

텔레그램 메시지는 `parse_mode=HTML`을 사용하며, 텔레그램에서 지원하는 제한된 태그만 활용합니다.

## 🔑 프로바이더 환경 변수 (Provider Environment)

```env
NEWS_API_BASE_URL=
NEWS_API_KEY=
SEC_USER_AGENT=DailyStockBriefing/0.1 contact@example.com
DART_API_KEY=
LLM_PROVIDER=auto
LLM_MODEL=llama-3.1-8b-instant
LLM_RPM_LIMIT=
GROQ_API_KEY=
NVIDIA_API_KEY=
NVIDIA_LLM_MODEL=
LLM_API_BASE_URL=
LLM_API_KEY=
```

* SEC 데이터는 API 키 없이 사용할 수 있으나, 책임 있는 `SEC_USER_AGENT` 설정이 필수적입니다.
* DART 실시간 호출을 위해서는 `DART_API_KEY`가 필요합니다.
* LLM을 통한 요약 및 강화(Enrichment)는 선택 사항이나, 인증 정보가 있을 경우 활성화됩니다.
  * `LLM_PROVIDER=auto`로 설정 시, `GROQ_API_KEY`가 존재하면 Groq을 우선 사용합니다 (기본 30 RPM 제한).
  * Groq 키가 없고 `NVIDIA_API_KEY`와 모델명이 설정되어 있으면 NVIDIA의 OpenAI 호환 엔드포인트를 사용합니다 (기본 40 RPM 제한).
  * `LLM_API_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`을 설정하여 범용 OpenAI 호환 엔드포인트를 사용할 수도 있습니다.

## 🔄 GitHub Actions 자동화

워크플로우는 매일 `23:00 UTC` (한국 시간 `08:00 KST`)에 실행됩니다.
매일 1회 실행되며 단일 통합 텔레그램 브리핑(메시지 + HTML 첨부)을 전송합니다.

**설정해야 할 Repository Secrets:**
* `TELEGRAM_BOT_TOKEN`
* `TELEGRAM_CHAT_ID`
* `NEWS_API_BASE_URL`
* `NEWS_API_KEY`
* `SEC_USER_AGENT`
* `DART_API_KEY`
* `GROQ_API_KEY`
* `LLM_MODEL`
* `LLM_RPM_LIMIT`
* `NVIDIA_API_KEY`
* `NVIDIA_LLM_MODEL`
* `LLM_API_BASE_URL`
* `LLM_API_KEY`

## ☁️ Oracle 서버 배포 (Oracle Server Deployment)

Oracle 서버 배포는 선택 사항입니다. GitHub Actions와 systemd에서 동일한 Python 진입점을 사용합니다.

권장 서버 경로:
```bash
/opt/briefstock
```

서버에 설치:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

`/opt/briefstock/.env` 파일을 생성하고 동일하게 환경 변수를 설정한 뒤, 타이머를 등록합니다:
```bash
sudo cp deploy/oracle/daily-stock-briefing.service /etc/systemd/system/
sudo cp deploy/oracle/daily-stock-briefing.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now daily-stock-briefing.timer
```

수동 서버 실행 방법:
```bash
bash deploy/oracle/run_daily_briefing.sh
```

## 🧪 테스트 (Tests)

```bash
.\.venv\Scripts\python.exe -m pytest tests -v
```

## 🗺️ 로드맵 (Roadmap)

* 일일 리포트 경로를 단순하게 유지하기 위해 이번 배치에서는 의도적으로 SQLite 상태 저장소를 구현하지 않았습니다. 향후 `price_snapshots`, `news_items`, `filing_items`, `company_events`, `provider_runs`, `daily_reports`, `follow_up_tasks` 등의 테이블이 추가될 예정입니다.
* LLM 출력 스키마 역시 의도적으로 변경하지 않았습니다. 추후 자유 형식의 `thesis_summary` 및 `follow_up_questions` 형태에서 구조화된 중요도/신뢰도(Materiality/Confidence) 스키마로 발전시킬 계획입니다.
