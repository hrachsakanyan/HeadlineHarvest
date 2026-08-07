"""Post-processing: de-duplication and keyword filtering."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit, urlunsplit

from .models import Article

logger = logging.getLogger(__name__)

#: Tracking parameters that change the URL without changing the article.
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref")


def canonical_url(url: str) -> str:
    """Strip tracking parameters, fragments and trailing slashes for comparison."""
    parts = urlsplit(url)
    query = "&".join(
        param
        for param in parts.query.split("&")
        if param and not param.lower().startswith(_TRACKING_PREFIXES)
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def normalise_title(title: str) -> str:
    """Lowercase, drop punctuation and collapse spaces, for comparison only."""
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


def deduplicate(articles: list[Article]) -> list[Article]:
    """Keep the first occurrence of each article.

    Two articles are the same if they share a canonical URL, or if they share a
    normalised title (the same story syndicated under two links).
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[Article] = []

    for article in articles:
        url_key = canonical_url(article.url)
        title_key = normalise_title(article.title)
        if url_key in seen_urls or (title_key and title_key in seen_titles):
            logger.debug("Duplicate dropped: %s", article.title)
            continue
        seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        unique.append(article)

    dropped = len(articles) - len(unique)
    if dropped:
        logger.info("Removed %s duplicate article(s)", dropped)
    return unique


def _keyword_pattern(keywords: list[str]) -> re.Pattern[str]:
    """One case-insensitive pattern matching any keyword as a whole word.

    The lookarounds stop "flu" from matching "influence", and unlike ``\\b`` they
    still work for terms that end in punctuation such as "c++". Multi-word
    phrases like "heart disease" are matched with flexible whitespace.
    """
    alternatives = [r"\s+".join(re.escape(word) for word in kw.split()) for kw in keywords]
    return re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(alternatives), re.IGNORECASE)


def filter_by_keywords(
    articles: list[Article], keywords: list[str], *, search_summary: bool = True
) -> list[Article]:
    """Keep only articles whose title (or summary) mentions a keyword."""
    if not keywords:
        return articles

    pattern = _keyword_pattern(keywords)
    kept = [
        article
        for article in articles
        if pattern.search(article.title)
        or (search_summary and pattern.search(article.summary))
    ]
    logger.info("Keyword filter kept %s of %s article(s)", len(kept), len(articles))
    return kept


def matched_keywords(article: Article, keywords: list[str]) -> list[str]:
    """Which keywords a given article matched - handy for debugging a filter."""
    haystack = f"{article.title} {article.summary}"
    return [kw for kw in keywords if _keyword_pattern([kw]).search(haystack)]
