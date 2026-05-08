from press_release_collector.collectors.html_collector import collect_html
from press_release_collector.collectors.rss_collector import collect_rss
from press_release_collector.collectors.wire_collector import collect_wire


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        return None


class _Client:
    def __init__(self, pages: dict[str, str], requests: list[str], **kwargs) -> None:
        self._pages = pages
        self._requests = requests

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str, **kwargs) -> _Response:
        self._requests.append(url)
        return _Response(self._pages[url])


def test_html_collector_prefers_internal_press_release_links(monkeypatch) -> None:
    listing_url = "https://www.csisoftware.com/category/press-releases/"
    release_url = "https://www.csisoftware.com/category/press-releases/2026/05/results"
    pages = {
        listing_url: f"""
        <html><body>
          <nav><a href="https://www.csisoftware.com/about-us">About Us</a></nav>
          <article><h2><a href="{release_url}">Constellation Announces Results for Q1</a></h2></article>
          <article><h2><a href="https://www.csisoftware.com/investor-deck.pdf">Investor Deck</a></h2></article>
        </body></html>
        """,
        release_url: """
        <html><body><main>
          <h1>Constellation Announces Results for Q1</h1>
          <time datetime="2026-05-08T10:00:00Z"></time>
          <p>© Copyright Constellation Software Inc. All Rights Reserved.</p>
          <p>Revenue increased 12% and cash flow improved.</p>
        </main></body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_html(
        ticker="CSU.TO",
        company_name="Constellation Software",
        url=listing_url,
    )

    assert requests == [listing_url, release_url]
    assert len(releases) == 2
    assert releases[0].title == "Constellation Announces Results for Q1"
    assert "Revenue increased" in releases[0].summary
    assert "Copyright" not in releases[0].summary
    assert releases[1].title == "Investor Deck"
    assert releases[1].url == "https://www.csisoftware.com/investor-deck.pdf"
    assert releases[1].summary is None


def test_rss_collector_returns_empty_on_failure(monkeypatch) -> None:
    def _boom(url: str):
        raise RuntimeError("network")

    monkeypatch.setattr("press_release_collector.collectors.rss_collector.feedparser.parse", _boom)

    assert collect_rss("CSU.TO", "Constellation Software", "https://example.com/rss") == []


def test_wire_collector_mvp_returns_empty_fallback() -> None:
    assert collect_wire("CSU.TO", "Constellation Software", ["Constellation Software"]) == []
