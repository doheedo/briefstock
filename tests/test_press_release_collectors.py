from press_release_collector.collectors.html_collector import collect_html
from press_release_collector.collectors import html_collector
from press_release_collector.collectors.globenewswire_collector import (
    collect_globenewswire_search,
)
from press_release_collector.collectors.nasdaq_collector import collect_nasdaq_press_releases
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


class _JsonResponse(_Response):
    def __init__(self, payload: dict, url: str = "") -> None:
        import json

        self._payload = payload
        super().__init__(json.dumps(payload), url=url)

    def json(self) -> dict:
        return self._payload


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


def test_nasdaq_collector_uses_press_release_api_and_detail_pages(monkeypatch) -> None:
    api_url = (
        "https://www.nasdaq.com/api/news/topic/press_release"
        "?q=symbol:SABR|assetclass:STOCKS&limit=2&offset=0"
    )
    detail_url = "https://www.nasdaq.com/press-release/sabre-results"
    requests: list[str] = []

    class _NasdaqClient:
        def __init__(self, **kwargs) -> None:
            self.headers = kwargs.get("headers") or {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str, **kwargs):
            requests.append(url)
            if url == api_url:
                return _JsonResponse(
                    {
                        "data": {
                            "rows": [
                                {
                                    "title": "Sabre Recognized in Gartnerĸį Magic Quadrantĸâ",
                                    "url": "/press-release/sabre-results",
                                    "created": "May 7, 2026",
                                }
                            ]
                        }
                    },
                    url=url,
                )
            return _Response(
                """
                <html><body><main>
                  <h1>Sabre Recognized in Gartnerĸį Magic Quadrantĸâ</h1>
                  <p>SOUTHLAKE, Texas, May 7, 2026 - Sabre reported revenue growth.</p>
                  <p>Management discussed demand and technology investments.</p>
                </main></body></html>
                """,
                url=detail_url,
            )

    monkeypatch.setattr(
        "press_release_collector.collectors.nasdaq_collector.httpx.Client",
        lambda **kwargs: _NasdaqClient(**kwargs),
    )

    releases = collect_nasdaq_press_releases("SABR", "Sabre Corporation", max_items=2)

    assert requests == [api_url, detail_url]
    assert releases[0].title == "Sabre Recognized in Gartner® Magic Quadrant™"
    assert releases[0].url == detail_url
    assert releases[0].published_at == "May 7, 2026"
    assert releases[0].source_type == "official_html"
    assert "Sabre reported revenue growth" in (releases[0].summary or "")


def test_globenewswire_collector_reads_search_result_cards(monkeypatch) -> None:
    search_url = "https://www.globenewswire.com/search/organization/condor"
    detail_url = (
        "https://www.globenewswire.com/news-release/2026/05/13/3294505/0/en/"
        "condor-announces-2026-first-quarter-results.html"
    )
    pages = {
        search_url: """
        <html><body>
          <div class="recentNewsH">
            <ul><li class="row">
              <div class="date-source">May 13, 2026 17:00 ET | Source: Condor Energies Inc.</div>
              <div class="mainLink">
                <a href="/news-release/2026/05/13/3294505/0/en/condor-announces-2026-first-quarter-results.html">
                  Condor Announces 2026 First Quarter Results
                </a>
              </div>
              <div class="newsTxt"><p>Condor reported first quarter production and financial results.</p></div>
            </li></ul>
          </div>
        </body></html>
        """
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.globenewswire_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_globenewswire_search(
        "CDR.TO",
        "Condor Energies Inc.",
        search_url,
        max_items=2,
    )

    assert requests == [search_url]
    assert releases[0].title == "Condor Announces 2026 First Quarter Results"
    assert releases[0].url == detail_url
    assert releases[0].published_at == "May 13, 2026"
    assert releases[0].source_type == "official_html"
    assert "production and financial results" in (releases[0].summary or "")


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


def test_html_collector_keeps_external_pdf_asset_links(monkeypatch) -> None:
    listing_url = "https://investor.bff.com/en/press-releases"
    pdf_url = (
        "https://edge.sitecorecloud.io/bffbanking/media/Project/BFFWebsites/"
        "investorrelations/Eng-PDF/Press-releases/2026/April/"
        "20260430_BFF---PR_BoD-approves-AR25.pdf"
    )
    pages = {
        listing_url: f"""
        <html><body>
          <main><a href="{pdf_url}">Download PDF</a></main>
        </body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_html(
        ticker="BFF.MI",
        company_name="BFF Bank",
        url=listing_url,
    )

    assert requests == [listing_url]
    assert releases[0].url == pdf_url
    assert releases[0].title == "20260430 Bff Pr Bod Approves Ar25"
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


def test_html_collector_skips_generic_detail_headings(monkeypatch) -> None:
    listing_url = "https://ir.upstart.com/news-and-events/news-releases"
    release_url = "https://ir.upstart.com/news-releases/news-release-details/upstart-announces-results"
    pages = {
        listing_url: f"""
        <html><body>
          <main><a href="{release_url}">Upstart Announces First Quarter 2026 Results</a></main>
        </body></html>
        """,
        release_url: """
        <html><head>
          <title>Upstart Announces First Quarter 2026 Results</title>
        </head><body><main>
          <h1>Release Details</h1>
          <p>Upstart reported revenue growth and improved adjusted EBITDA.</p>
        </main></body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_html(
        ticker="UPST",
        company_name="Upstart",
        url=listing_url,
    )

    assert releases[0].title == "Upstart Announces First Quarter 2026 Results"
    assert "revenue growth" in releases[0].summary


def test_html_collector_filters_cenovus_listing_navigation(monkeypatch) -> None:
    listing_url = "https://www.cenovus.com/Investors/Financial-results-and-reports"
    release_url = "https://www.cenovus.com/News-and-Stories/News-releases/2026/3288594"
    pages = {
        listing_url: f"""
        <html><body>
          <main>
            <a href="{release_url}">Cenovus announces first-quarter 2026 results</a>
            <a href="/Investors/Financial-results-and-reports/Archived-annual-documents-for-acquired-companies">Archived annual documents</a>
            <a href="/News-and-Stories">News and stories</a>
          </main>
        </body></html>
        """,
        release_url: """
        <html><body><main>
          <h1>Cenovus announces first-quarter 2026 results</h1>
          <p>Cenovus reported upstream production and financial results for the quarter.</p>
        </main></body></html>
        """,
    }
    requests: list[str] = []
    monkeypatch.setattr(
        "press_release_collector.collectors.html_collector.httpx.Client",
        lambda **kwargs: _Client(pages, requests, **kwargs),
    )

    releases = collect_html(
        ticker="CVE",
        company_name="Cenovus",
        url=listing_url,
    )

    assert [release.url for release in releases] == [release_url]


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

    monkeypatch.setattr("press_release_collector.collectors.rss_collector.FEEDPARSER_AVAILABLE", True)
    monkeypatch.setattr("press_release_collector.collectors.rss_collector.feedparser.parse", _boom)
    monkeypatch.setattr("press_release_collector.collectors.rss_collector.httpx.get", _boom)

    assert collect_rss("CSU.TO", "Constellation Software", "https://example.com/rss") == []


def test_rss_collector_uses_xml_fallback_when_feedparser_missing(monkeypatch) -> None:
    class _XmlResponse:
        content = b"""
        <rss><channel><item>
          <title>Uber Announces Results</title>
          <link>https://investor.uber.com/news/results</link>
          <pubDate>Fri, 08 May 2026 12:00:00 GMT</pubDate>
          <description>Revenue increased during the quarter.</description>
        </item></channel></rss>
        """

        def raise_for_status(self) -> None:
            return None

    def _boom(url: str):
        raise RuntimeError("feedparser missing")

    monkeypatch.setattr("press_release_collector.collectors.rss_collector.FEEDPARSER_AVAILABLE", False)
    monkeypatch.setattr("press_release_collector.collectors.rss_collector.feedparser.parse", _boom)
    monkeypatch.setattr(
        "press_release_collector.collectors.rss_collector.httpx.get",
        lambda *args, **kwargs: _XmlResponse(),
    )

    releases = collect_rss("UBER", "Uber", "https://investor.uber.com/rss")

    assert releases[0].title == "Uber Announces Results"
    assert releases[0].url == "https://investor.uber.com/news/results"
    assert "Revenue increased" in releases[0].summary


def test_rss_collector_xml_fallback_resolves_relative_links(monkeypatch) -> None:
    class _XmlResponse:
        content = b"""
        <rss><channel><item>
          <title>Pinterest Announces Results</title>
          <link>/files/doc_earnings/2026/q1/earnings-result/Q126-PressRelease.pdf</link>
        </item></channel></rss>
        """

        def raise_for_status(self) -> None:
            return None

    def _boom(url: str):
        raise RuntimeError("feedparser missing")

    monkeypatch.setattr("press_release_collector.collectors.rss_collector.FEEDPARSER_AVAILABLE", False)
    monkeypatch.setattr("press_release_collector.collectors.rss_collector.feedparser.parse", _boom)
    monkeypatch.setattr(
        "press_release_collector.collectors.rss_collector.httpx.get",
        lambda *args, **kwargs: _XmlResponse(),
    )

    releases = collect_rss("PINS", "Pinterest", "https://investor.pinterestinc.com/rss/pressrelease.aspx")

    assert (
        releases[0].url
        == "https://investor.pinterestinc.com/files/doc_earnings/2026/q1/earnings-result/Q126-PressRelease.pdf"
    )


def test_rss_collector_sanitizes_html_summary_from_feedparser(monkeypatch) -> None:
    html_summary = """
    <span>
      <div class="q4default">
        <p><i>Q1 Revenue of $1,008 million, an increase of 18%</i></p>
        <ul><li>Global Monthly Active Users increased 11% to 631 million.</li></ul>
      </div>
    </span>
    """

    class _Entry:
        title = "Pinterest Announces First Quarter 2026 Results"
        link = "/files/doc_earnings/2026/q1/earnings-result/Q126-PressRelease.pdf"
        published = "Mon, 04 May 2026 20:05:00 GMT"
        summary = html_summary
        content = [{"value": html_summary * 200}]

    monkeypatch.setattr("press_release_collector.collectors.rss_collector.FEEDPARSER_AVAILABLE", True)
    monkeypatch.setattr(
        "press_release_collector.collectors.rss_collector.feedparser.parse",
        lambda url: type("_Feed", (), {"entries": [_Entry()]})(),
    )

    releases = collect_rss(
        "PINS",
        "Pinterest",
        "https://investor.pinterestinc.com/rss/pressrelease.aspx",
    )

    assert releases[0].summary.startswith("Q1 Revenue of $1,008 million")
    assert "<" not in releases[0].summary
    assert "q4default" not in releases[0].summary
    assert len(releases[0].summary) <= 500
    assert releases[0].content == releases[0].summary


def test_rss_collector_filters_google_news_noise(monkeypatch) -> None:
    class _XmlResponse:
        content = b"""
        <rss><channel>
          <item>
            <title>Berkshire Hathaway Inc. First Quarter 2026 Earnings Release - ChartMill</title>
            <link>https://news.google.com/rss/articles/good</link>
          </item>
          <item>
            <title>Berkshire Hathaway: Greg Abel Wins Big In Q1 - Seeking Alpha</title>
            <link>https://news.google.com/rss/articles/noise</link>
          </item>
        </channel></rss>
        """

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr("press_release_collector.collectors.rss_collector.FEEDPARSER_AVAILABLE", False)
    monkeypatch.setattr(
        "press_release_collector.collectors.rss_collector.httpx.get",
        lambda *args, **kwargs: _XmlResponse(),
    )

    releases = collect_rss(
        "BRK-B",
        "Berkshire Hathaway",
        "https://news.google.com/rss/search?q=berkshire",
    )

    assert [release.title for release in releases] == [
        "Berkshire Hathaway Inc. First Quarter 2026 Earnings Release - ChartMill"
    ]


def test_wire_collector_mvp_returns_empty_fallback() -> None:
    assert collect_wire("CSU.TO", "Constellation Software", ["Constellation Software"]) == []
