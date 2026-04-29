# Briefstock

Daily delta briefing for a fixed stock watchlist. The job collects price snapshots, news, SEC/DART filings, classifies company events, writes JSON/HTML reports, and sends a short Telegram HTML summary.

The price layer also tracks 5D, 1M, and 1Y returns, benchmark performance, relative 1Y performance, RSI(14), and 1Y PNG charts generated directly from yfinance data with matplotlib. Google image/chart crawling is not used.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

Create `.env` from `.env.example` and fill only the providers you use.

## Configuration

Edit `config/watchlist.yaml`.

Each item requires:

- `ticker`
- `name`
- `market`
- `thesis`
- `keywords`
- `source_priority`

Optional fields include `group`, `aliases`, `exclude_keywords`, `thesis_questions`, `red_flags`, `positive_signals`, and `min_keyword_matches`.

## Local Run

```powershell
.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-25 --skip-telegram
```

Run with an optional group argument (ignored in unified delivery mode):

```powershell
.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-25 --group data_info --skip-telegram
```

Outputs:

- `reports/html/YYYY-MM-DD.html`
- `reports/json/YYYY-MM-DD.json`
- `reports/charts/YYYY-MM-DD/{ticker}.png`

`--group` is accepted for backward compatibility but ignored. The pipeline always writes a single consolidated output per run.

## Reports

HTML reports include the full watchlist slice plus each available 1Y chart. Chart images are embedded into the HTML file as base64 data URIs so Telegram `sendDocument` can deliver a self-contained report. Telegram messages keep only compact numeric summaries and attach the HTML report instead of sending every chart image.

Each price section includes:

- Price and 1D change
- 5D, 1M, and 1Y return
- Benchmark 1Y return using `^GSPC` for non-Korean tickers and `^KS200` for Korean tickers
- Relative 1Y return versus the selected benchmark
- RSI(14)

Ownership filings such as Form 3, Form 4, Form 5, Form 144, and ownership documents are kept short by default. The report treats related news as the primary summary source; if there is no related news, the filing is shown as a low-priority ownership/insider filing instead of expanding the raw filing text.

## Telegram

Create a bot with BotFather, send a message to the bot, then get your chat id. Set:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Send a test message:

```powershell
.\.venv\Scripts\python.exe scripts\send_telegram_test.py
```

Telegram messages use `parse_mode=HTML` and only limited Telegram-supported tags.

## Provider Environment

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

SEC can be used without an API key, but requires a responsible `SEC_USER_AGENT`. DART live calls require `DART_API_KEY`.

LLM enrichment is optional but enabled when credentials are present. With `LLM_PROVIDER=auto`, the job uses Groq first when `GROQ_API_KEY` exists, with a default 30 RPM guard. If Groq is absent and `NVIDIA_API_KEY` plus a model are present, it uses NVIDIA's OpenAI-compatible endpoint with a default 40 RPM guard. Generic OpenAI-compatible endpoints can be used by setting `LLM_API_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.

## GitHub Actions

The workflow runs daily at `23:00 UTC`, which is `08:00 Asia/Seoul`.

The workflow runs once per day and sends one consolidated Telegram briefing (DM + HTML attachment).

Set these repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NEWS_API_BASE_URL`
- `NEWS_API_KEY`
- `SEC_USER_AGENT`
- `DART_API_KEY`
- `GROQ_API_KEY`
- `LLM_MODEL`
- `LLM_RPM_LIMIT`
- `NVIDIA_API_KEY`
- `NVIDIA_LLM_MODEL`
- `LLM_API_BASE_URL`
- `LLM_API_KEY`

## Oracle Server Deployment

The Oracle server is optional. The same Python entrypoint is used by GitHub Actions and systemd.

Suggested server path:

```bash
/opt/briefstock
```

Install on the server:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Create `/opt/briefstock/.env` with the same environment variables. Then install the timer:

```bash
sudo cp deploy/oracle/daily-stock-briefing.service /etc/systemd/system/
sudo cp deploy/oracle/daily-stock-briefing.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now daily-stock-briefing.timer
```

Manual server run:

```bash
bash deploy/oracle/run_daily_briefing.sh
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

## Roadmap

SQLite state storage is intentionally not implemented in this batch to keep the daily report path simple. Planned tables: `price_snapshots`, `news_items`, `filing_items`, `company_events`, `provider_runs`, `daily_reports`, and `follow_up_tasks`.

The LLM output schema is also intentionally unchanged. A future version can move from free-form `thesis_summary` and `follow_up_questions` to a structured materiality/confidence schema.
