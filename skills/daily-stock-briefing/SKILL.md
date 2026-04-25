---
name: daily-stock-briefing
description: Repeatable workflow for maintaining the briefstock daily stock briefing repository.
---

1. Read `config/watchlist.yaml` before changing briefing behavior.
2. Keep provider-specific logic inside `src/daily_stock_briefing/adapters/`.
3. Keep classification and priority rules inside `src/daily_stock_briefing/services/`.
4. Keep Telegram HTML limited to supported tags.
5. Do not hardcode secrets; use `.env`, GitHub Secrets, or server environment files.
6. Run the narrowest relevant pytest target after each code edit.
7. Preserve the product shape: daily delta briefing, not deep-dive research.
