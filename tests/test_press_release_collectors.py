from press_release_collector.collectors.html_collector import collect_html
from press_release_collector.collectors import html_collector
from press_release_collector.collectors.rss_collector import collect_rss
from press_release_collector.collectors.wire_collector import collect_wire
from press_release_collector.core.normalize import normalize_press_release


class _Response:
    def __init__(self, text: str, url: str = "") -> None:
        self.text = text
        self.content = text.encode("utf-8")
        self.url = url

    def raise_for_status(self) -> None:
        return None


class _Client:
    def __init__(self, pages: dict[str, str], requests: list[str], **kwargs) -> None:
        self._pages = pages
        self._requests = requests
        self.headers = kwargs.get("headers") or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str, **kwargs) -> _Response:
        self._requests.append(url)
        return _Response(self._pages[url], url=url)


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


def test_html_collector_uses_clear_user_agent_and_skips_self_fragments(
    monkeypatch,
) -> None:
    listing_url = "https://ir.roblox.com/news/default.aspx"
    release_url = "https://ir.roblox.com/news/press-release-details/2026/results.aspx"
    clients: list[_Client] = []
    pages = {
        listing_url: f"""
        <html><body>
          <main>
            <a href="#main-content">News</a>
            <article><h2><a href="{release_url}">Roblox Reports Financial Results</a></h2></article>
          </main>
        </body></html>
        """,
        release_url: """
        <html><body><main>
          <h1>Roblox Reports Financial Results</h1>
          <time datetime="2026-05-08"></time>
          <p>Revenue and bookings increased during the quarter.</p>
        </main></body></html>
        """,
    }
    requests: list[str] = []

    def _client(**kwargs):
        client = _Client(pages, requests, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        _client,
    )

    releases = collect_html(
        ticker="RBLX",
        company_name="Roblox",
        url=listing_url,
    )

    assert requests == [listing_url, release_url]
    assert clients[0].headers["User-Agent"].startswith("briefstock-press-release-collector")
    assert len(releases) == 1
    assert releases[0].title == "Roblox Reports Financial Results"


def test_html_collector_does_not_match_press_inside_unrelated_words(
    monkeypatch,
) -> None:
    listing_url = "https://www.hdfcbank.com/personal/about-us/investor-relations/financial-results"
    release_url = "https://www.hdfcbank.com/content/results/press-release-q1"
    pages = {
        listing_url: f"""
        <html><body>
          <main>
            <a href="/xpressway/insta-services/update-nominee">Update Nominee</a>
            <a href="{release_url}"></a>
          </main>
        </body></html>
        """,
        release_url: """
        <html><body><main>
          <h1>Press Release Q1</h1>
          <p>HDFC Bank reported quarterly financial results for the period.</p>
        </main></body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_html(
        ticker="HDB",
        company_name="HDFC Bank",
        url=listing_url,
    )

    assert requests == [listing_url, release_url]
    assert len(releases) == 1
    assert releases[0].url == release_url
    assert releases[0].title == "Press Release Q1"


def test_html_collector_keeps_pdf_links_without_fetching_or_summary(monkeypatch) -> None:
    listing_url = "https://www.hdfcbank.com/personal/about-us/investor-relations/financial-results"
    pdf_url = "https://www.hdfcbank.com/content/results/press-release-q1.pdf"
    pages = {
        listing_url: f"""
        <html><body>
          <main>
            <a href="{pdf_url}">Press Release Q1</a>
          </main>
        </body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_html(
        ticker="HDB",
        company_name="HDFC Bank",
        url=listing_url,
    )

    assert requests == [listing_url]
    assert len(releases) == 1
    assert releases[0].url == pdf_url
    assert releases[0].title == "Press Release Q1"
    assert releases[0].summary is None


def test_html_collector_falls_back_to_all_links_and_filters_ir_noise(
    monkeypatch,
) -> None:
    listing_url = "https://www.icici.bank.in/about-us/invest-relations"
    presentation_url = (
        "https://www.icici.bank.in/content/dam/icicibank/india/managed-assets/docs/"
        "about-us/2026/2026_01_Q3-2026_investor-presentation.pdf"
    )
    results_url = (
        "https://www.icici.bank.in/content/dam/icicibank/india/managed-assets/docs/"
        "about-us/2026/icici-bank-financial-results-q3-2026.pdf"
    )
    subsidiary_url = (
        "https://www.icici.bank.in/content/dam/icicibank/india/managed-assets/docs/"
        "about-us/2025/lombard-investor-presentation-dec2025.pdf"
    )
    pages = {
        listing_url: f"""
        <html><body>
          <main><a href="/about-us/investor">Investor Presentations</a></main>
          <section>
            <a href="{presentation_url}">VIEW PRESENTATION</a>
            <a href="{results_url}">ICICI Bank: Financial Results for quarter ended December 31, 2025 PDF 259 KB</a>
            <a href="{subsidiary_url}">ICICI Lombard General: Investor Presentation for quarter ended December 31, 2025 PDF 4.08 MB</a>
            <a href="/about-us/voting-result">Voting Results</a>
          </section>
        </body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_html(
        ticker="IBN",
        company_name="ICICI Bank Limited ADR",
        url=listing_url,
    )

    assert requests == [listing_url]
    assert [release.url for release in releases] == [presentation_url, results_url]
    assert all(release.summary is None for release in releases)


def test_html_collector_uses_url_date_when_page_has_no_time(monkeypatch) -> None:
    listing_url = "https://www.csisoftware.com/category/press-releases/"
    release_url = "https://www.csisoftware.com/category/press-releases/2026/03/09/results"
    pages = {
        listing_url: f"""
        <html><body>
          <article><h2><a href="{release_url}">Constellation Announces Results</a></h2></article>
        </body></html>
        """,
        release_url: """
        <html><body><main>
          <h1>Constellation Announces Results</h1>
          <p>Revenue increased and cash flow improved during the quarter.</p>
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

    assert releases[0].published_at == "2026-03-09"
    assert normalize_press_release(releases[0]).published_at == "2026-03-09T00:00:00+00:00"


def test_html_collector_prefers_paragraphs_when_extracted_text_is_navigation(
    monkeypatch,
) -> None:
    listing_url = "https://www.csisoftware.com/category/press-releases/"
    release_url = "https://www.csisoftware.com/category/press-releases/2026/04/10/meetings"
    pages = {
        listing_url: f"""
        <html><body>
          <article><h2><a href="{release_url}">Constellation Announces Annual Meetings</a></h2></article>
        </body></html>
        """,
        release_url: """
        <html><body><main>
          <h1>Constellation Announces Annual Meetings</h1>
          <p>TORONTO, CANADA - Constellation Software announced its annual shareholder meetings.</p>
          <p>Meeting materials will be available to shareholders before the record date.</p>
        </main></body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )
    class _FakeTrafilatura:
        @staticmethod
        def extract(*args, **kwargs):
            return (
            "About Us Overview Being Acquired Management Team Contact Us ESG "
            "Our Companies News Investor Relations Statutory Filings"
            )

    monkeypatch.setattr(html_collector, "trafilatura", _FakeTrafilatura)

    releases = collect_html(
        ticker="CSU.TO",
        company_name="Constellation Software",
        url=listing_url,
    )

    assert "annual shareholder meetings" in releases[0].summary
    assert "About Us Overview" not in releases[0].summary


def test_rss_collector_returns_empty_on_failure(monkeypatch) -> None:
    def _boom(url: str):
        raise RuntimeError("network")

    monkeypatch.setattr("press_release_collector.collectors.rss_collector.feedparser.parse", _boom)

    assert collect_rss("CSU.TO", "Constellation Software", "https://example.com/rss") == []


def test_wire_collector_mvp_returns_empty_fallback() -> None:
    assert collect_wire("CSU.TO", "Constellation Software", ["Constellation Software"]) == []
