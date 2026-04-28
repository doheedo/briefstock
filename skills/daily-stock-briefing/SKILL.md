---
name: daily-stock-briefing
description: Repeatable workflow for maintaining the briefstock daily stock briefing repository.
---

1. Read `config/watchlist.yaml` before changing briefing behavior.
2. Keep provider-specific logic inside `src/daily_stock_briefing/adapters/`.
3. Keep classification and priority rules inside `src/daily_stock_briefing/services/`.
4. Keep Telegram HTML limited to supported tags.
5. Use `^GSPC` as the US benchmark and `^KS200` for Korean names via price job logic; label display follows `benchmark_display_name` / `benchmark_ticker`.
6. Generate charts with yfinance history and matplotlib under `reports/charts/`; do not scrape Google images.
7. Do not send every chart image to Telegram; keep Telegram short and rely on the HTML attachment.
8. Do not hardcode secrets; use `.env`, GitHub Secrets, or server environment files.
9. Run the narrowest relevant pytest target after each code edit.
10. Preserve the product shape: daily delta briefing, not deep-dive research.
