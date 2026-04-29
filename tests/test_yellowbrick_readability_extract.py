from daily_stock_briefing.adapters.yellowbrick import readability_extract


def test_find_recent_read_more_candidate_parses_listing(monkeypatch) -> None:
    html = """
    <html><body>
      <div>
        <span>April 20, 2026</span>
        <a href="/articles/csu-idea">Read full article</a>
      </div>
    </body></html>
    """

    class _Resp:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, _url: str):
            return _Resp(html)

    monkeypatch.setattr(readability_extract.httpx, "Client", lambda **kwargs: _Client())
    candidate = readability_extract.find_recent_read_more_candidate("CSU", days=30)

    assert candidate is not None
    assert candidate.read_more_url == "https://www.joinyellowbrick.com/articles/csu-idea"
    assert candidate.pitch_date == "2026-04-20"

