"""Fetching pages and turning their HTML into :class:`Article` objects."""

from __future__ import annotations

import logging
import random
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .config import DEFAULT_USER_AGENT, Source
from .models import Article
from .robots import RobotsPolicy

logger = logging.getLogger(__name__)

#: Prefer lxml when it is installed; html.parser always ships with Python.
try:  # pragma: no cover - depends on the environment
    import lxml  # noqa: F401

    HTML_PARSER = "lxml"
except ImportError:  # pragma: no cover
    HTML_PARSER = "html.parser"

#: Date formats seen on the default sources, tried in order.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%b. %d, %Y",   # Aug. 3, 2026
    "%b %d, %Y",    # Aug 3, 2026
    "%B %d, %Y",    # August 3, 2026
    "%d %B %Y",     # 3 August 2026
    "%d %b %Y",     # 3 Aug 2026
    "%m/%d/%Y",
)

#: Statuses that are worth retrying: transient server-side or rate limiting.
_RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchError(Exception):
    """Raised when a page could not be retrieved after all retries."""


def build_session(user_agent: str = DEFAULT_USER_AGENT) -> requests.Session:
    """A session with a self-identifying User-Agent and connection reuse."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def fetch_page(
    session: requests.Session,
    url: str,
    *,
    timeout: float = 15.0,
    retries: int = 2,
    backoff: float = 2.0,
) -> str:
    """Download ``url`` and return its decoded HTML.

    Retries transient failures with exponential backoff. Raises
    :class:`FetchError` when every attempt fails.
    """
    last_error = "unknown error"

    for attempt in range(retries + 1):
        if attempt:
            wait = backoff * (2 ** (attempt - 1))
            logger.info("Retry %s/%s for %s in %.1fs", attempt, retries, url, wait)
            time.sleep(wait)
        try:
            response = session.get(url, timeout=timeout)
        except requests.Timeout:
            last_error = f"timed out after {timeout}s"
            continue
        except requests.RequestException as exc:
            last_error = f"request failed ({exc})"
            continue

        if response.status_code in _RETRY_STATUSES:
            last_error = f"HTTP {response.status_code}"
            continue
        if response.status_code >= 400:
            # 404, 403 and friends will not fix themselves - stop immediately.
            raise FetchError(f"{url} -> HTTP {response.status_code}")

        # requests falls back to ISO-8859-1 when the server sends no charset,
        # which mangles curly quotes and accents. Sniff the body instead.
        if "charset" not in response.headers.get("Content-Type", "").lower():
            response.encoding = response.apparent_encoding or response.encoding
        return response.text

    raise FetchError(f"{url} -> {last_error} (gave up after {retries + 1} attempts)")


#: Zero-width characters that survive parsing and pollute a CSV silently.
_INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF],  # ZWSP, ZWNJ, ZWJ, word joiner, BOM
    None,
)


def _fix_mojibake(text: str) -> str:
    """Repair Windows-1252 bytes that a site published as UTF-8.

    Real pages do this: ScienceDaily emits ``\\xc2\\x97`` for an em dash, which
    decodes to U+0097 - a control character that no amount of ``strip()`` will
    remove. Map that range back through cp1252, dropping anything undefined.
    """
    def repair(match: re.Match[str]) -> str:
        try:
            return match.group(0).encode("latin-1").decode("cp1252")
        except UnicodeDecodeError:
            return ""

    return re.sub("[\u0080-\u009f]", repair, text)


def clean_text(text: str) -> str:
    """Normalise scraped text: repair mojibake, drop invisibles, collapse space."""
    text = _fix_mojibake(text).translate(_INVISIBLE)
    return re.sub(r"\s+", " ", text).strip()  # \s also covers &nbsp; and friends


def _select_text(item: Tag, selector: str) -> str:
    """Text of the first match for ``selector``, cleaned up."""
    if not selector:
        return ""
    node = item.select_one(selector)
    if node is None:
        return ""
    return clean_text(node.get_text(" ", strip=True))


def _select_attr(item: Tag, selector: str, attr: str) -> str:
    """Value of ``attr`` on the first match for ``selector``."""
    if not selector:
        return ""
    node = item.select_one(selector)
    if node is None:
        return ""
    value = node.get(attr, "")
    if isinstance(value, list):  # e.g. class="a b" comes back as a list
        value = " ".join(value)
    return clean_text(value)


def normalise_date(raw: str) -> str:
    """Best-effort conversion of a date string to ``YYYY-MM-DD``.

    Returns ``""`` when the format is not recognised - the original text is
    still preserved in ``Article.published_raw``.
    """
    text = raw.strip()
    if not text:
        return ""

    # Trim ISO timestamps ("2026-08-03T10:30:00+00:00") down to the seconds part.
    iso_candidate = text.replace("Z", "").split("+")[0].strip()
    for fmt in _DATE_FORMATS:
        for candidate in (text, iso_candidate):
            try:
                return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

    # Fall back to pulling a "Month D, YYYY" or "YYYY-MM-DD" out of longer text.
    match = re.search(r"([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})|(\d{4}-\d{2}-\d{2})", text)
    if match and match.group(0) != text:
        return normalise_date(match.group(0))
    return ""


#: Punctuation sites use to separate a date from the text that follows it.
_SEPARATORS = " -‐–—|·:"


def _trim_separators(text: str) -> str:
    """Drop a trailing "  " / " - " style separator from a date string."""
    return text.rstrip(_SEPARATORS)


def _clean_summary(summary: str, date_text: str) -> str:
    """Drop the date prefix some sites embed at the start of the summary."""
    if date_text and summary.startswith(date_text):
        summary = summary[len(date_text):]
    return summary.lstrip("  -–—|").strip()


def parse_articles(html: str, source: Source) -> list[Article]:
    """Turn a page of HTML into articles, skipping unusable entries."""
    soup = BeautifulSoup(html, HTML_PARSER)
    items = soup.select(source.item_selector)
    if not items:
        logger.warning(
            "No elements matched %r on %s - the site layout may have changed",
            source.item_selector,
            source.name,
        )
        return []

    articles: list[Article] = []
    skipped = 0

    for item in items:
        title = _select_text(item, source.title_selector)
        link = _select_attr(item, source.link_selector, source.link_attr)

        # A headline with no text or no link is not a usable record.
        if not title or not link:
            skipped += 1
            logger.debug("Skipping item on %s (title=%r link=%r)", source.name, title, link)
            continue

        if source.date_attr:
            raw_date = _select_attr(item, source.date_selector, source.date_attr)
        else:
            raw_date = _select_text(item, source.date_selector)

        # The untrimmed text is what the summary is prefixed with, so strip the
        # prefix first and only then tidy the date we store.
        summary = _clean_summary(_select_text(item, source.summary_selector), raw_date)
        raw_date = _trim_separators(raw_date)

        articles.append(
            Article(
                title=title,
                url=requests.compat.urljoin(source.url, link),  # relative -> absolute
                published=normalise_date(raw_date),
                published_raw=raw_date,
                summary=summary,
                source=source.name,
            )
        )

    if skipped:
        logger.info("%s: skipped %s item(s) with no title or link", source.name, skipped)
    return articles


def polite_sleep(seconds: float, *, jitter: float = 0.3) -> None:
    """Wait between requests, with a little jitter so traffic is not robotic."""
    if seconds <= 0:
        return
    delay = seconds + random.uniform(0, jitter)
    logger.debug("Sleeping %.2fs before the next request", delay)
    time.sleep(delay)


def scrape_source(
    source: Source,
    session: requests.Session,
    robots: RobotsPolicy,
    *,
    default_delay: float = 2.0,
    timeout: float = 15.0,
    retries: int = 2,
) -> list[Article]:
    """Scrape a single source, honouring robots.txt and its crawl-delay.

    Returns an empty list (rather than raising) when the site disallows us or
    the fetch fails, so one bad source never aborts the whole run.
    """
    if not robots.can_fetch(source.url):
        logger.warning("robots.txt disallows %s - skipping %s", source.url, source.name)
        return []

    # The site's own Crawl-delay always wins if it is longer than ours.
    delay = source.delay if source.delay is not None else default_delay
    site_delay = robots.crawl_delay(source.url)
    if site_delay is not None and site_delay > delay:
        logger.info("%s asks for a %.0fs crawl-delay - honouring it", source.name, site_delay)
        delay = site_delay

    logger.info("Fetching %s (%s)", source.name, source.url)
    try:
        html = fetch_page(session, source.url, timeout=timeout, retries=retries)
    except FetchError as exc:
        logger.error("Could not fetch %s: %s", source.name, exc)
        return []

    articles = parse_articles(html, source)
    logger.info("%s: found %s article(s)", source.name, len(articles))

    polite_sleep(delay)
    return articles


def scrape_sources(
    sources: list[Source],
    session: requests.Session,
    robots: RobotsPolicy,
    **kwargs,
) -> list[Article]:
    """Scrape every enabled source in turn."""
    collected: list[Article] = []
    for source in sources:
        if not source.enabled:
            logger.debug("Skipping disabled source %s", source.name)
            continue
        collected.extend(scrape_source(source, session, robots, **kwargs))
    return collected
