from pathlib import Path

from jinja2 import Template

from daily_stock_briefing.domain.models import DailyBriefingReport

PAGE = Template(
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
      {% else %}
      <p class="muted">Price: unavailable</p>
      {% endif %}
      <p><strong>Thesis Impact:</strong> {{ briefing.thesis_summary }}</p>
      {% if briefing.derived_events %}
      <h3>Events</h3>
      {% for event in briefing.derived_events %}
      <p><strong>{{ event.category.value }}</strong> / score {{ event.importance_score }} / {{ event.thesis_impact.value }}<br>
      {{ event.summary }}</p>
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
    path.write_text(PAGE.render(report=report), encoding="utf-8")
    return path
