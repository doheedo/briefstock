# Daily Stock Briefing Design

## Goal

Build a Codex-manageable Python repository that produces a once-daily briefing for a fixed watchlist and sends a short Telegram summary plus a full HTML report.

This system is not a deep research generator. It is a delta briefing system for already-researched companies. The primary job is to surface today's important price moves, news, filings, and company events, then judge whether they matter to the user's existing thesis.

## Product Scope

### Primary outputs

- Short Telegram summary using Telegram Bot API `parse_mode=HTML`
- Full HTML report written to `reports/html/YYYY-MM-DD.html`
- Structured JSON artifact written to `reports/json/YYYY-MM-DD.json`

### Core user outcomes

- Maintain watchlist in `config/watchlist.yaml`
- Run one daily batch job
- Receive a concise update on what changed today
- See thesis-relevant impact rather than a full fresh investment memo
- Attach the HTML report to Telegram when the message is too long or when richer detail is useful

### Out of scope for MVP

- Full portfolio management
- Deep valuation models
- Intraday streaming
- Autonomous trade decisions
- Database-backed event warehouse

## Design Principles

- Prefer the smallest safe change that solves the task
- Use provider adapters so data sources can be swapped later
- Keep the system runnable end-to-end with reference adapters
- Use rules first for scoring and classification; keep LLM integration optional
- Focus on high-signal daily changes, not broad company background
- Store secrets only in environment variables and GitHub Secrets

## Reference Influence from External Repositories

These repositories inform structure, not copied implementation.

- `ZhuLinsen/daily_stock_analysis`: end-to-end scheduled workflow, config-driven runs, multi-channel delivery
- `miaohancheng/llm_stock_report`: batch-job layout, Actions-first automation, report generation and delivery separation
- `samgozman/fin-thread`: collector/composer/publisher separation for feed generation
- `stefanoamorelli/sec-edgar-agentkit`: SEC-specific adapter boundary and filing access patterns
- `E9Technologies/ED-ALPHA`: event extraction pipeline and importance scoring concept
- `tradermonty/claude-trading-skills`: skill-based repeatable workflow guidance
- `kesslerio/finance-news-openclaw-skill`: news aggregation and messaging-oriented briefing patterns
- `openclaw yahoo-finance skill`: lightweight Yahoo Finance reference usage
- `jjlabsio/korea-stock-mcp`: DART/KRX split and large-document handling approach for Korean disclosures

## Architecture

Recommended approach: port-and-adapter batch application.

### High-level flow

`watchlist -> market snapshot -> per-symbol collection -> dedupe -> event classification -> thesis impact scoring -> priority scoring -> render -> Telegram publish`

### Repository shape

```text
.
├─ .github/workflows/
├─ config/
├─ docs/
├─ reports/
├─ scripts/
├─ skills/daily-stock-briefing/
├─ src/daily_stock_briefing/
│  ├─ adapters/
│  ├─ domain/
│  ├─ jobs/
│  ├─ renderers/
│  └─ services/
├─ tests/
├─ .env.example
├─ AGENTS.md
├─ README.md
└─ pyproject.toml
```

### Module boundaries

- `domain`
  - Typed models and enums only
- `adapters/prices`
  - Price provider interface
  - Reference `yfinance` implementation
  - Future KRX adapter slot
- `adapters/news`
  - News provider interface
  - Reference HTTP/news-search implementation
  - Common deduper
- `adapters/filings`
  - `sec` adapter
  - `dart` adapter
- `adapters/llm`
  - Provider-neutral summarize/classify interface
  - Optional in MVP runtime path
- `adapters/telegram`
  - Message send and document send
- `services`
  - Watchlist loading
  - Event normalization
  - Rule-based classification
  - Thesis impact and priority scoring
- `renderers`
  - Telegram HTML renderer
  - Full HTML report renderer
- `jobs`
  - Daily orchestration entrypoint

## Data Model

### Watchlist

Managed in `config/watchlist.yaml`.

Each item contains:

- `ticker`
- `name`
- `market`
- `thesis`
- `keywords`
- `source_priority`

Example `source_priority`:

```yaml
source_priority:
  - filings
  - news
  - price
```

### Core domain entities

- `WatchlistItem`
  - ticker, name, market, thesis, keywords, source_priority
- `PriceSnapshot`
  - ticker, previous_close, close, change, change_pct, currency, as_of, source
- `NewsItem`
  - id, ticker, title, summary, publisher, url, canonical_url, published_at, source, matched_keywords
- `FilingItem`
  - id, ticker, filing_type, title, filed_at, event_date, filing_url, source_system, raw_excerpt
- `CompanyEvent`
  - ticker, category, importance_score, thesis_impact, summary, evidence, source_refs
- `SymbolBriefing`
  - watchlist item, price snapshot, major_news, filings, derived_events, thesis_summary, follow_up_questions, priority
- `DailyBriefingReport`
  - run_date, market_summary, symbol_briefings, delivery_metadata

## Data Collection Strategy

### Prices

Reference adapter:

- `yfinance` for daily price snapshots

Design constraints:

- Normalize to a common snapshot shape
- Use previous close vs latest close for daily move
- Keep adapter boundary explicit so KRX official API can be added later without service rewrites

### News

Reference adapter:

- HTTP-based provider adapter with configurable provider implementation

MVP requirement:

- Must deduplicate articles before rendering

Deduplication strategy:

- canonical URL normalization
- normalized title comparison
- near-duplicate collapse inside a publish-time window
- source-domain canonicalization for syndication cases

Deduped output should prefer the article with the best source quality according to symbol `source_priority` and provider ranking.

### Filings

Reference adapters:

- SEC filing adapter
- DART filing adapter

Design constraints:

- Common normalized filing output across both regions
- Keep raw links to source systems
- Support extracting a short excerpt for briefing use
- Avoid mandatory full-document parsing for very large filings

For Korean disclosures, large documents should support a section-oriented workflow rather than eager full extraction. This follows the practical lesson from `korea-stock-mcp`.

## Event Classification

Allowed categories are fixed:

- `earnings`
- `guidance`
- `regulation`
- `litigation`
- `mna`
- `product`
- `customer_contract`
- `management`
- `financing`
- `insider_transaction`
- `macro_exposure`
- `noise`

### Classification policy

- Rules-first classification in MVP
- Optional LLM adapter can assist with summarization and ambiguous cases
- If confidence is low, keep the event but classify thesis impact as `unknown`

## Scoring and Prioritization

### Importance score

Range: `1` to `5`

- `5`: earnings, guidance, major M&A, major regulation/litigation, large financing, or any event likely to materially change the investment case
- `4`: meaningful product launch, major contract, management change, notable insider transaction, meaningful filing-based update
- `3`: relevant but moderate developments, standard press coverage, or noticeable price move requiring attention
- `2`: minor update, low-value follow-on story, weakly relevant coverage
- `1`: clear noise

### Thesis impact

Allowed values:

- `positive`
- `negative`
- `neutral`
- `unknown`

Interpretation:

- `positive`: reinforces the current thesis
- `negative`: weakens or challenges the current thesis
- `neutral`: new information but not thesis-critical
- `unknown`: insufficient clarity to judge direction yet

### Daily priority

Allowed values:

- `High`
- `Medium`
- `Low`

Rules:

- `High` if any event has `importance_score >= 4`
- `High` if any meaningful event has `thesis_impact = negative`
- `Medium` if the main developments are around score `3` or there are unresolved follow-up questions
- `Low` if there are no meaningful changes beyond noise or small price movement

## Output Design

### Market summary

Keep minimal and practical:

- major relevant indices
- broad market direction
- optionally FX/rates if useful to covered names

### Per-symbol briefing format

Balanced format, not ultra-short and not long-form.

For each symbol include:

- price move
- major news
- filings/company events
- thesis impact
- follow-up questions
- daily priority

### Telegram HTML format

Use only Telegram-supported limited HTML tags:

- `<b>`
- `<i>`
- `<u>`
- `<s>`
- `<code>`
- `<pre>`
- `<a>`

Do not use:

- `<ul>`
- `<li>`
- `<table>`
- `<style>`
- `<script>`

Implementation notes:

- Use plain text bullets such as `•`
- Keep each symbol section compact
- If message is too long, send a compressed summary and attach the full HTML report with `sendDocument`

### HTML report

Write to `reports/html/YYYY-MM-DD.html`.

HTML report includes:

- market summary
- per-symbol cards or sections
- source links
- fuller evidence and notes than Telegram

The HTML report can be more expressive than Telegram, but should still remain clean and lightweight.

## User Experience Model

The system assumes the user already knows the companies. Therefore:

- avoid long company background explanations
- avoid deep-dive memo style by default
- optimize for "what changed today and why it matters"
- use `thesis` only as a lens for impact judgment, not as a prompt to rewrite the investment case

## Automation and Operations

### Local execution

Primary job:

- `python -m daily_stock_briefing.jobs.run_daily_briefing --date YYYY-MM-DD`

Support scripts:

- Telegram send test script
- sample report generation script

### GitHub Actions

Run daily at Korea time 08:00.

Because GitHub Actions cron uses UTC, schedule:

- `0 23 * * *`

This corresponds to 08:00 KST on the next calendar day.

Workflow responsibilities:

- install project
- load secrets from GitHub Secrets
- run daily briefing job
- persist report artifacts

## Security

- Never hardcode API keys
- Never hardcode Telegram bot token
- Provide only `.env.example`
- Use GitHub Secrets in CI
- Keep provider adapters configurable by environment variables

## MVP Deliverables

- Executable minimal Python repository
- sample `config/watchlist.yaml`
- sample HTML report
- Telegram delivery test script
- GitHub Actions workflow
- `README.md`
- `AGENTS.md`
- `skills/daily-stock-briefing/SKILL.md`

## Testing Strategy

Start narrow.

- unit tests for watchlist loading
- unit tests for news deduplication
- unit tests for event classification and priority rules
- renderer tests for Telegram-safe HTML
- one integration-style smoke test using sample data

If no live provider credentials are present, tests should run on fixtures and mocks.

## Error Handling

- Provider failures should degrade gracefully by source
- A failed news adapter should not block filing or price sections
- Missing LLM configuration should not block rule-based briefing generation
- Telegram send failure should preserve generated local artifacts

The final report should include run warnings when any source is unavailable.

## Open Implementation Decisions Already Resolved

- Build a Python repository, not a multi-service platform
- Use adapter structure because provider choices are user-owned
- Use real reference adapters for prices and filings in MVP
- Support both SEC and DART in MVP
- Use rules-first scoring rather than LLM-first scoring
- Optimize for daily issue briefing, not deep research
- Default report style is balanced summary per symbol

## Implementation Readiness

This scope is suitable for a single implementation plan. It does not require decomposition into multiple projects yet.
