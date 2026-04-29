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


def test_find_recent_read_more_candidate_parses_next_payload(monkeypatch) -> None:
    html = r'''
    <html><body>
      <script>self.__next_f.push([1,"1c:[\"$\",\"div\",null,{\"children\":[[\"$\",\"$L1e\",null,{\"initialStockPitches\":[{\"id\":134526,\"url\":\"https://reboundcapital.substack.com/p/rebound-portfolio?utm_source=yellowbrick\",\"updatedAt\":\"2026-04-29T02:44:59.67068+00:00\",\"condensedText\":\"$1f\",\"dateOriginal\":\"2026-04-22\",\"dateRetrieved\":\"2026-04-24\",\"priceTarget\":4000,\"sentiment\":\"bullish\",\"source\":\"BLOG\",\"title\":\"Deep Dive: Constellation Software ($CSU)\",\"wordCount\":2603,\"readTime\":9,\"oneLinerText\":\"CSU.TO deep dive: VMS roll-up with 500+ acquisitions and 100% upside.\"}]}]]}}"])</script>
    </body></html>
    '''

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
    assert (
        candidate.read_more_url
        == "https://reboundcapital.substack.com/p/rebound-portfolio?utm_source=yellowbrick"
    )
    assert candidate.pitch_date == "2026-04-22"
    assert candidate.title == "Deep Dive: Constellation Software ($CSU)"
    assert candidate.teaser is not None
    assert "VMS roll-up" in candidate.teaser


def test_extract_readable_text_passes_html_text_to_readability(monkeypatch) -> None:
    html = """
    <html><body><article>
      <h1>Pitch</h1>
      <p>Constellation Software compounds through vertical market software acquisitions.</p>
    </article></body></html>
    """

    class _Resp:
        text = html

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, _url: str):
            return _Resp()

    monkeypatch.setattr(readability_extract.httpx, "Client", lambda **kwargs: _Client())

    text = readability_extract.extract_readable_text("https://example.com/pitch")

    assert "Constellation Software compounds" in text

