from pathlib import Path

from jinja2 import Environment, select_autoescape

from daily_stock_briefing.domain.models import DailyBriefingReport


def _format_pct(value: float | None, *, suffix: str = "%") -> str:
    return "n/a" if value is None else f"{value:+.1f}{suffix}"


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"

PAGE = Environment(autoescape=select_autoescape(["html", "xml"])).from_string(
    """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Stock Briefing - {{ report.run_date }}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1d1d1f; }
    main { max-width: 960px; margin: 0 auto; }
    section { border-top: 1px solid #ddd; padding: 20px 0; }
    .priority { font-weight: 700; }
    .muted { color: #666; }
    .metrics { line-height: 1.6; }
    img.chart { width: 100%; max-width: 900px; height: auto; border: 1px solid #e5e5e5; border-radius: 8px; }
  </style>
</head>
<body>
  <main>
    <h1>Daily Stock Briefing - {{ report.run_date }}</h1>
    <p>{{ report.market_summary }}</p>
    {% for briefing in report.symbol_briefings %}
    <section>
      <h2>{{ briefing.watchlist_item.ticker }} - {{ briefing.watchlist_item.name }}</h2>
      <p class="priority">Priority: {{ briefing.priority.value }}</p>
      {% if briefing.price_snapshot %}
      <p>Price: {{ "%.2f"|format(briefing.price_snapshot.close) }} {{ briefing.price_snapshot.currency }}
        ({{ "%+.1f"|format(briefing.price_snapshot.change_pct) }}%)</p>
      <p class="metrics">
        5D: {{ format_pct(briefing.price_snapshot.return_5d_pct) }} /
        1M: {{ format_pct(briefing.price_snapshot.return_1m_pct) }} /
        1Y: {{ format_pct(briefing.price_snapshot.return_1y_pct) }}<br>
        S&amp;P500 1Y: {{ format_pct(briefing.price_snapshot.benchmark_return_1y_pct) }} /
        Relative: {{ format_pct(briefing.price_snapshot.relative_return_1y_pct, suffix="%p") }}<br>
        RSI(14): {{ format_number(briefing.price_snapshot.rsi_14) }}
      </p>
      {% if briefing.price_snapshot.chart_path %}
      <p><img class="chart" src="{{ briefing.price_snapshot.chart_path }}" alt="{{ briefing.watchlist_item.ticker }} 1Y price and RSI chart"></p>
      {% endif %}
      {% else %}
      <p class="muted">Price: unavailable</p>
      {% endif %}
      <p><strong>Thesis Impact:</strong> {{ briefing.thesis_summary }}</p>
      {% if briefing.derived_events %}
      <h3>Events</h3>
      {% for event in briefing.derived_events %}
      <p><strong>{{ event.category.value }}</strong> / score {{ event.importance_score }} / {{ event.thesis_impact.value }}<br>
      {{ event.summary }}</p>
      {% if event.source_refs %}
      <p class="muted">Sources:
      {% for url in event.source_refs %}
        <a href="{{ url }}">{{ loop.index }}</a>
      {% endfor %}
      </p>
      {% endif %}
      {% endfor %}
      {% endif %}
      {% if briefing.follow_up_questions %}
      <h3>Follow-up</h3>
      {% for question in briefing.follow_up_questions %}
      <p>{{ question }}</p>
      {% endfor %}
      {% endif %}
    </section>
    {% endfor %}
  </main>
</body>
</html>
"""
)


def write_html_report(report: DailyBriefingReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        PAGE.render(report=report, format_pct=_format_pct, format_number=_format_number),
        encoding="utf-8",
    )
    return path
