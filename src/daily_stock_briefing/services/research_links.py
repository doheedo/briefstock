"""research_links.py

종목별 외부 리서치 링크를 순수 함수로 생성합니다.
네트워크 호출 없음. API 키 불필요.
"""
from __future__ import annotations

from urllib.parse import quote, quote_plus

from daily_stock_briefing.domain.models import ResearchLinks, WatchlistItem

# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

_KR_MARKETS = {"KR"}
_US_MARKETS = {"US", "USA"}
_CA_MARKETS = {"CA", "CANADA"}


def _q(text: str) -> str:
    """URL query-string 인코딩 (공백 → +)."""
    return quote_plus(text, safe="")


def _qpath(text: str) -> str:
    """URL 경로 세그먼트 인코딩 (공백 → %20)."""
    return quote(text, safe="")


def _base_ticker(ticker: str) -> str:
    """'CSU.TO' → 'CSU', '012700.KQ' → '012700'"""
    return ticker.split(".")[0]


def _x_keyword_query(item: WatchlistItem) -> str:
    """x_query 필드가 있으면 우선 사용, 없으면 name + ticker 조합."""
    if item.x_query:
        return item.x_query
    parts: list[str] = []
    if item.name:
        parts.append(item.name)
    base = _base_ticker(item.ticker)
    if base and base not in item.name:
        parts.append(base)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# 링크 생성 함수 (시장 중립)
# ---------------------------------------------------------------------------

def _google_search_url(name: str, ticker: str) -> str | None:
    query = " ".join(filter(None, [name, _base_ticker(ticker)]))
    if not query.strip():
        return None
    return f"https://www.google.com/search?q={_q(query)}"


def _google_news_url(name: str, ticker: str) -> str | None:
    query = " ".join(filter(None, [name, _base_ticker(ticker)]))
    if not query.strip():
        return None
    return f"https://www.google.com/search?q={_q(query)}&tbm=nws"


def _x_search_url(query: str) -> str | None:
    if not query.strip():
        return None
    return f"https://x.com/search?q={_q(query)}&f=live"


def _x_cashtag_url(ticker: str) -> str | None:
    base = _base_ticker(ticker)
    if not base:
        return None
    return f"https://x.com/search?q=%24{_qpath(base)}&f=live"


def _yellowbrick_portal_url(ticker: str) -> str | None:
    """Yellowbrick ticker portal."""
    base = _base_ticker(ticker)
    if not base:
        return None
    return f"https://www.joinyellowbrick.com/?ticker={_qpath(base)}"


def yellowbrick_portal_url(ticker: str) -> str | None:
    """Public helper for Yellowbrick ticker portal links."""
    return _yellowbrick_portal_url(ticker)


def _yahoo_finance_url(ticker: str) -> str | None:
    if not ticker:
        return None
    return f"https://finance.yahoo.com/quote/{_qpath(ticker)}"


# Yahoo-style ticker suffix → Google Finance exchange code.
_SUFFIX_TO_GOOGLE_EXCHANGE: dict[str, str] = {
    "TO": "TSX",
    "V": "CVE",
    "CN": "CNSX",
    "NE": "NEO",
    "AS": "AMS",
    "L": "LON",
    "SW": "SWX",
    "KS": "KRX",
    "KQ": "KRX",
}


def _google_finance_url(ticker: str, market: str) -> str | None:
    """Google Finance는 'SYMBOL:EXCHANGE' 형식을 선호. 접미사가 있으면 접미사 우선."""
    base = _base_ticker(ticker)
    if not base:
        return None
    gf_ticker: str | None = None
    if "." in ticker:
        suf = ticker.rsplit(".", 1)[-1].upper()
        ex = _SUFFIX_TO_GOOGLE_EXCHANGE.get(suf)
        if ex:
            gf_ticker = f"{base}:{ex}"
    if gf_ticker is None:
        exchange_map: dict[str, str] = {
            "KR": "KRX",
            "US": "NASDAQ",
            "CA": "TSX",
            "NL": "AMS",
            "DE": "ETR",
            "CN": "SHE",
        }
        exchange = exchange_map.get(market.upper())
        gf_ticker = f"{base}:{exchange}" if exchange else base
    return f"https://www.google.com/finance/quote/{_qpath(gf_ticker)}"


def _sec_edgar_url(name: str) -> str | None:
    if not name:
        return None
    return (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?company={_q(name)}&CIK=&type=10-K&dateb=&owner=include"
        "&count=10&search_text=&action=getcompany"
    )


def _dart_search_url(name: str) -> str | None:
    if not name:
        return None
    return f"https://dart.fss.or.kr/dsab001/search.ax?textCrpNm={_q(name)}"


def _naver_finance_url(ticker: str) -> str | None:
    """네이버증권: 종목코드 숫자 부분(6자리)만 사용."""
    base = _base_ticker(ticker)
    if not base or not base.isdigit():
        return None
    return f"https://finance.naver.com/item/main.naver?code={base}"


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def build_research_links(item: WatchlistItem) -> ResearchLinks:  # noqa: C901
    """
    WatchlistItem 하나를 받아 ResearchLinks를 반환합니다.
    실패해도 빈 ResearchLinks를 반환하며 예외를 전파하지 않습니다.
    """
    try:
        return _build(item)
    except Exception:  # pragma: no cover — defensive
        return ResearchLinks()


def _build(item: WatchlistItem) -> ResearchLinks:
    ticker = item.ticker
    name = item.name
    market = (item.market or "").upper()

    base = _base_ticker(ticker)
    kw_query = _x_keyword_query(item)

    is_kr = market in _KR_MARKETS
    is_us = market in _US_MARKETS

    # 공통 링크
    google = _google_search_url(name, ticker)
    google_news = _google_news_url(name, ticker)
    x_search = _x_search_url(kw_query) if kw_query else None
    x_cashtag = _x_cashtag_url(ticker) if base else None
    yellowbrick_search = _yellowbrick_portal_url(ticker)
    yahoo_finance = _yahoo_finance_url(ticker)
    google_finance = _google_finance_url(ticker, market)

    # 시장별 분기
    sec: str | None = None
    dart: str | None = None
    naver_finance: str | None = None

    if is_kr:
        dart = _dart_search_url(name)
        naver_finance = _naver_finance_url(ticker)
        # KR은 SEC 불필요
        sec = None
    elif is_us:
        sec = _sec_edgar_url(name)
        dart = None
    # CA/NL/DE/CN 등: SEC/DART 모두 null

    return ResearchLinks(
        google=google,
        google_news=google_news,
        x_search=x_search,
        x_cashtag=x_cashtag,
        yellowbrick_search=yellowbrick_search,
        sec=sec,
        dart=dart,
        yahoo_finance=yahoo_finance,
        google_finance=google_finance,
        naver_finance=naver_finance,
    )
