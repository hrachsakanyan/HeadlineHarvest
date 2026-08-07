"""Parsing, date normalisation and fetch behaviour."""

from __future__ import annotations

import pytest
import requests

from src.config import Source
from src.scraper import (
    FetchError,
    clean_text,
    fetch_page,
    normalise_date,
    parse_articles,
)


class FakeResponse:
    def __init__(self, status_code=200, text="<html></html>", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"


class FakeSession:
    """Replays a scripted list of responses/exceptions, one per call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# --- parsing ---------------------------------------------------------------

def test_parses_every_usable_item(sample_html, sample_source):
    articles = parse_articles(sample_html, sample_source)
    # 8 blocks in the fixture, minus the one with no link and the one with no title.
    assert len(articles) == 6


def test_skips_items_without_a_title_or_link(sample_html, sample_source):
    titles = [a.title for a in parse_articles(sample_html, sample_source)]
    assert "Sponsored Placeholder Without A Link" not in titles
    assert all(title for title in titles)


def test_relative_links_become_absolute(sample_html, sample_source):
    articles = parse_articles(sample_html, sample_source)
    first = articles[0]
    assert first.url == "https://example.com/releases/2026/08/260802223417.htm"


def test_absolute_links_are_left_alone(sample_html, sample_source):
    urls = [a.url for a in parse_articles(sample_html, sample_source)]
    assert "https://example.org/news/vaccine-trial" in urls


def test_missing_date_leaves_empty_fields_not_none(sample_html, sample_source):
    article = next(
        a for a in parse_articles(sample_html, sample_source)
        if a.title.startswith("Quantum")
    )
    assert article.published == ""
    assert article.published_raw == ""
    assert "published" in article.missing_fields


def test_unparseable_date_keeps_the_raw_text(sample_html, sample_source):
    article = next(
        a for a in parse_articles(sample_html, sample_source)
        if a.title.startswith("Cardiology")
    )
    assert article.published_raw == "3 hours ago"
    assert article.published == ""


def test_date_prefix_is_stripped_from_the_summary(sample_html, sample_source):
    article = parse_articles(sample_html, sample_source)[0]
    assert article.published == "2026-08-03"
    assert article.summary.startswith("Low arginine levels")


def test_date_can_be_read_from_an_attribute(sample_html, sample_source):
    sample_source.date_attr = "datetime"
    article = next(
        a for a in parse_articles(sample_html, sample_source)
        if a.title.startswith("Gene Therapy")
    )
    assert article.published == "2026-07-29"


def test_unmatched_item_selector_returns_empty_list(sample_html, sample_source):
    sample_source.item_selector = ".this-class-does-not-exist"
    assert parse_articles(sample_html, sample_source) == []


def test_source_defaults_link_selector_to_title_selector():
    source = Source(
        name="x", url="https://e.com", item_selector="li", title_selector="a.headline"
    )
    assert source.link_selector == "a.headline"


# --- text cleaning ---------------------------------------------------------

def test_clean_text_collapses_whitespace_and_nbsp():
    assert clean_text("  Two\n\tspaced" + chr(0xA0) + "words  ") == "Two spaced words"


def test_clean_text_repairs_cp1252_mojibake():
    # ScienceDaily really does publish U+0097 where it means an em dash.
    assert clean_text("Aug. 3, 2026 " + chr(0x97)) == "Aug. 3, 2026 —"


def test_clean_text_drops_undefined_control_characters():
    assert clean_text("head" + chr(0x8F) + "line") == "headline"


def test_clean_text_removes_zero_width_characters():
    assert clean_text("head" + chr(0x200B) + "line" + chr(0xFEFF)) == "headline"


def test_clean_text_keeps_hyphens_and_real_dashes():
    assert clean_text("Once-a-week workout — results") == "Once-a-week workout — results"


def test_trailing_separator_is_trimmed_from_the_date():
    html = """
    <div class="col-md-6">
      <div class="latest-head"><a href="/x">Title</a></div>
      <div class="latest-summary">
        <span class="story-date">Aug. 3, 2026 {sep}</span> The body text.
      </div>
    </div>
    """.format(sep=chr(0x97))
    source = Source(
        name="s", url="https://e.com/", item_selector=".col-md-6",
        title_selector=".latest-head a", date_selector=".story-date",
        summary_selector=".latest-summary",
    )
    article = parse_articles(html, source)[0]
    assert article.published_raw == "Aug. 3, 2026"
    assert article.published == "2026-08-03"
    assert article.summary == "The body text."


# --- date normalisation ----------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Aug. 3, 2026", "2026-08-03"),
        ("August 3, 2026", "2026-08-03"),
        ("July 31, 2026", "2026-07-31"),
        ("2026-08-03", "2026-08-03"),
        ("2026-08-03T14:25:30+00:00", "2026-08-03"),
        ("3 August 2026", "2026-08-03"),
        ("08/03/2026", "2026-08-03"),
        ("Published on Aug. 3, 2026 by staff", "2026-08-03"),
        ("3 hours ago", ""),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalise_date(raw, expected):
    assert normalise_date(raw) == expected


# --- fetching --------------------------------------------------------------

def test_fetch_returns_html_on_success():
    session = FakeSession([FakeResponse(text="<html>ok</html>")])
    assert fetch_page(session, "https://e.com", retries=0) == "<html>ok</html>"


def test_fetch_retries_transient_errors_then_succeeds():
    session = FakeSession([FakeResponse(status_code=503), FakeResponse(text="<html>ok</html>")])
    assert fetch_page(session, "https://e.com", retries=1, backoff=0) == "<html>ok</html>"
    assert session.calls == 2


def test_fetch_does_not_retry_a_404():
    session = FakeSession([FakeResponse(status_code=404)])
    with pytest.raises(FetchError, match="404"):
        fetch_page(session, "https://e.com", retries=3, backoff=0)
    assert session.calls == 1


def test_fetch_gives_up_after_retries():
    session = FakeSession([requests.Timeout(), requests.Timeout()])
    with pytest.raises(FetchError, match="timed out"):
        fetch_page(session, "https://e.com", timeout=1, retries=1, backoff=0)
    assert session.calls == 2


def test_encoding_is_sniffed_when_the_server_omits_a_charset():
    response = FakeResponse(headers={"Content-Type": "text/html"})
    response.apparent_encoding = "utf-8"
    response.encoding = "ISO-8859-1"
    session = FakeSession([response])
    fetch_page(session, "https://e.com", retries=0)
    assert response.encoding == "utf-8"
