## Operating principles

- Prefer the smallest safe change that solves the task.
- Inspect before editing.
- Explain the cause of an error before proposing a fix.
- Do not introduce unrelated refactors.
- Keep output concise and concrete.

## Python environment

- On Windows, use `.\.venv\Scripts\python.exe` when `.venv` exists.
- If `.venv` is missing, create it first with `py -m venv .venv`.
- Do not install packages outside the project virtual environment.

## Daily briefing conventions

- Treat this as a delta briefing system, not a deep research system.
- Preserve adapter boundaries under `src/daily_stock_briefing/adapters/`.
- Keep Telegram output compatible with Telegram Bot API `parse_mode=HTML`.
- Do not put `<ul>`, `<li>`, `<table>`, `<style>`, or `<script>` in Telegram messages.
- Never hardcode API keys or Telegram tokens.

## Validation

- Run the narrowest relevant pytest target after edits.
- For full local validation, run:
  `.\.venv\Scripts\python.exe -m pytest tests -v`
- SEC can be smoke-tested without an API key.
- DART live tests require `DART_API_KEY`; keep it in `.env` or process env only.
