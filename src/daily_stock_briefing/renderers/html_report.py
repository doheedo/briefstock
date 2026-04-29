import base64
from pathlib import Path

from jinja2 import Environment, select_autoescape

from daily_stock_briefing.domain.models import DailyBriefingReport
from daily_stock_briefing.services.benchmark_display import benchmark_display_name


def _priority_label(value: str) -> str:
    return {"High": "높음", "Medium": "중간", "Low": "낮음"}.get(value, value)


def _format_pct(value: float | None, *, suffix: str = "%") -> str:
    return "n/a" if value is None else f"{value:+.1f}{suffix}"


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _chart_src(chart_path: str | None, report_path: Path) -> str | None:
    if not chart_path:
        return None
    chart_file = Path(chart_path)
    if not chart_file.is_absolute():
        chart_file = report_path.parent / chart_file
    try:
        data = chart_file.read_bytes()
    except OSError:
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


PAGE = Environment(autoescape=select_autoescape(["html", "xml"])).from_string(
    """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>데일리 종목 브리핑 - {{ report.run_date }}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1d1d1f; }
    main { max-width: 960px; margin: 0 auto; }
    section { border-top: 1px solid #ddd; padding: 20px 0; }
    .priority { font-weight: 700; }
    .muted { color: #666; }
    .metrics { line-height: 1.6; }
    img.chart { width: 100%; max-width: 900px; height: auto; border: 1px solid #e5e5e5; border-radius: 8px; }
    .research-links { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; }
    .research-links a { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.8rem; text-decoration: none; background: #f0f0f5; color: #333; border: 1px solid #d0d0e0; }
    .research-links a:hover { background: #e0e0f0; }
  </style>
</head>
<body>
  <main>
    <h1>데일리 종목 브리핑 - {{ report.run_date }}</h1>
    <p>{{ report.market_summary }}</p>
    {% if report.wagn_holdings %}
    <section>
      <h2>WAGN ETF Holdings 모니터링</h2>
      <p>{{ report.wagn_holdings.summary_ko }}</p>
      <p class="muted">
        기준일: {{ report.wagn_holdings.as_of_date or "n/a" }} /
        전체 종목 수: {{ report.wagn_holdings.total_holdings }}
      </p>
      <p class="muted">
        출처:
        <a href="{{ report.wagn_holdings.source_url }}" target="_blank" rel="noopener">Fund Summary</a> /
        <a href="{{ report.wagn_holdings.download_url }}" target="_blank" rel="noopener">Download Full Holdings</a>
      </p>
      {% if report.wagn_holdings.error %}
      <p class="muted">{{ report.wagn_holdings.error }}</p>
      {% endif %}
      {% if report.wagn_holdings.notable_changes %}
      <h3>비중/구성 변화</h3>
      {% for ch in report.wagn_holdings.notable_changes %}
      <p>
        <strong>{{ ch.ticker }}</strong> {{ ch.name }}:
        {% if ch.change_type == "added" %}
        신규 편입 (현재 {{ format_pct(ch.current_weight_pct) }})
        {% elif ch.change_type == "removed" %}
        제외 (이전 {{ format_pct(ch.previous_weight_pct) }})
        {% else %}
        {{ format_pct(ch.previous_weight_pct) }} → {{ format_pct(ch.current_weight_pct) }}
        ({{ format_pct(ch.delta_pct, suffix="%p") }})
        {% endif %}
      </p>
      {% endfor %}
      {% endif %}
      {% if report.wagn_holdings.top_holdings %}
      <h3>상위 보유 비중</h3>
      {% for item in report.wagn_holdings.top_holdings[:10] %}
      <p>{{ item.ticker }} {{ item.name }}: {{ format_pct(item.weight_pct) }}</p>
      {% endfor %}
      {% endif %}
    </section>
    {% endif %}
    {% for briefing in report.symbol_briefings %}
    <section>
      <h2>{{ briefing.watchlist_item.ticker }} - {{ briefing.watchlist_item.name }}</h2>
      <p class="priority">우선순위: {{ priority_label(briefing.priority.value) }}</p>
      {% if briefing.price_snapshot %}
      <p>가격: {{ "%.2f"|format(briefing.price_snapshot.close) }} {{ briefing.price_snapshot.currency }}
        ({{ "%+.1f"|format(briefing.price_snapshot.change_pct) }}%)</p>
      <p class="metrics">
        5D: {{ format_pct(briefing.price_snapshot.return_5d_pct) }} /
        1M: {{ format_pct(briefing.price_snapshot.return_1m_pct) }} /
        1Y: {{ format_pct(briefing.price_snapshot.return_1y_pct) }}<br>
        {{ benchmark_label(briefing.price_snapshot) }} 1Y: {{ format_pct(briefing.price_snapshot.benchmark_return_1y_pct) }} /
        Relative: {{ format_pct(briefing.price_snapshot.relative_return_1y_pct, suffix="%p") }}<br>
        RSI(14): {{ format_number(briefing.price_snapshot.rsi_14) }}
      </p>
      {% set chart_data_src = chart_src(briefing.price_snapshot.chart_path) %}
      {% if chart_data_src %}
      <p><img class="chart" src="{{ chart_data_src }}" alt="{{ briefing.watchlist_item.ticker }} 1년 가격 및 RSI 차트"></p>
      {% endif %}
      {% else %}
      <p class="muted">가격: n/a</p>
      {% endif %}
      <p><strong>Thesis 영향:</strong> {{ briefing.thesis_summary }}</p>
      {% if briefing.derived_events %}
      <h3>회사 이벤트</h3>
      {% for event in briefing.derived_events %}
      <p><strong>{{ event.category.value }}</strong> / score {{ event.importance_score }} / {{ event.thesis_impact.value }}<br>
      {{ event.summary }}</p>
      {% if event.source_refs %}
      <p class="muted">출처:
      {% for url in event.source_refs %}
        <a href="{{ url }}">{{ loop.index }}</a>
      {% endfor %}
      </p>
      {% endif %}
      {% endfor %}
      {% endif %}
      {% if briefing.follow_up_questions %}
      <h3>추가 확인</h3>
      {% for question in briefing.follow_up_questions %}
      <p>{{ question }}</p>
      {% endfor %}
      {% endif %}
      {% set rl = briefing.research_links %}
      {% if rl.google or rl.google_news or rl.x_search or rl.x_cashtag or rl.yellowbrick_search or rl.sec or rl.dart or rl.yahoo_finance or rl.google_finance or rl.naver_finance %}
      <div class="research-links">
        {% if rl.google %}<a href="{{ rl.google }}" target="_blank" rel="noopener">Google</a>{% endif %}
        {% if rl.google_news %}<a href="{{ rl.google_news }}" target="_blank" rel="noopener">News</a>{% endif %}
        {% if rl.x_search %}<a href="{{ rl.x_search }}" target="_blank" rel="noopener">X 검색</a>{% endif %}
        {% if rl.x_cashtag %}<a href="{{ rl.x_cashtag }}" target="_blank" rel="noopener">${{ briefing.watchlist_item.ticker.split('.')[0] }}</a>{% endif %}
        {% if rl.yellowbrick_search %}<a href="{{ rl.yellowbrick_search }}" target="_blank" rel="noopener">🟡 YellowBrick</a>{% endif %}
        {% if rl.dart %}<a href="{{ rl.dart }}" target="_blank" rel="noopener">DART</a>{% endif %}
        {% if rl.sec %}<a href="{{ rl.sec }}" target="_blank" rel="noopener">SEC</a>{% endif %}
        {% if rl.yahoo_finance %}<a href="{{ rl.yahoo_finance }}" target="_blank" rel="noopener">Yahoo Finance</a>{% endif %}
        {% if rl.google_finance %}<a href="{{ rl.google_finance }}" target="_blank" rel="noopener">Google Finance</a>{% endif %}
        {% if rl.naver_finance %}<a href="{{ rl.naver_finance }}" target="_blank" rel="noopener">네이버증권</a>{% endif %}
      </div>
      {% endif %}
      {% if briefing.yellowbrick_pitch %}
      <h3>Yellowbrick 피칭 (최근 30일)</h3>
      <p class="muted">포털: <a href="{{ briefing.yellowbrick_pitch.search_url }}" target="_blank" rel="noopener">joinyellowbrick.com</a></p>
      {% if briefing.yellowbrick_pitch.article_url %}
      <p class="muted">원문: <a href="{{ briefing.yellowbrick_pitch.article_url }}" target="_blank" rel="noopener">링크</a>{% if briefing.yellowbrick_pitch.pitch_date %} (피칭일 {{ briefing.yellowbrick_pitch.pitch_date }}){% endif %}</p>
      {% endif %}
      {% if briefing.yellowbrick_pitch.error %}
      <p class="muted">{{ briefing.yellowbrick_pitch.error }}</p>
      {% elif briefing.yellowbrick_pitch.summary_ko %}
      <p><strong>요약:</strong> {{ briefing.yellowbrick_pitch.summary_ko }}</p>
      {% if briefing.yellowbrick_pitch.source_excerpt_en %}
      <p class="muted"><strong>원문 추출 일부:</strong> {{ briefing.yellowbrick_pitch.source_excerpt_en[:500] }}{% if briefing.yellowbrick_pitch.source_excerpt_en|length > 500 %}...{% endif %}</p>
      {% endif %}
      {% endif %}
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
        PAGE.render(
            report=report,
            format_pct=_format_pct,
            format_number=_format_number,
            priority_label=_priority_label,
            chart_src=lambda chart_path: _chart_src(chart_path, path),
            benchmark_label=lambda ps: benchmark_display_name(ps.benchmark_ticker)
            if ps
            else "Benchmark",
        ),
        encoding="utf-8",
    )
    return path
