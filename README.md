# Briefstock

Daily delta briefing for a fixed stock watchlist. The job collects price snapshots, news, SEC/DART filings, classifies company events, writes JSON/HTML reports, and sends a short Telegram HTML summary.

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

## Local Run

```powershell
.\.venv\Scripts\python.exe -m daily_stock_briefing.jobs.run_daily_briefing --date 2026-04-25 --skip-telegram
```

Outputs:

- `reports/html/YYYY-MM-DD.html`
- `reports/json/YYYY-MM-DD.json`

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
```

SEC can be used without an API key, but requires a responsible `SEC_USER_AGENT`. DART live calls require `DART_API_KEY`.

## GitHub Actions

The workflow runs daily at `23:00 UTC`, which is `08:00 Asia/Seoul`.

Set these repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NEWS_API_BASE_URL`
- `NEWS_API_KEY`
- `SEC_USER_AGENT`
- `DART_API_KEY`

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
