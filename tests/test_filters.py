"""De-duplication and keyword filtering."""

from __future__ import annotations

import pytest

from src.filters import (
    canonical_url,
    deduplicate,
    filter_by_keywords,
    matched_keywords,
    normalise_title,
)
from src.models import Article
from src.scraper import parse_articles


def make(title: str, url: str, summary: str = "") -> Article:
    return Article(title=title, url=url, summary=summary)


# --- URL canonicalisation --------------------------------------------------

@pytest.mark.parametrize(
    "a,b",
    [
        ("https://e.com/story", "https://e.com/story/"),
        ("https://e.com/story", "https://e.com/story?utm_source=twitter"),
        ("https://e.com/story", "https://e.com/story#comments"),
        ("https://E.com/story", "https://e.com/story"),
        ("https://e.com/story?id=7", "https://e.com/story?id=7&fbclid=xyz"),
    ],
)
def test_urls_that_should_compare_equal(a, b):
    assert canonical_url(a) == canonical_url(b)


def test_meaningful_query_parameters_are_kept():
    assert canonical_url("https://e.com/s?id=7") != canonical_url("https://e.com/s?id=8")


def test_normalise_title_ignores_case_and_punctuation():
    assert normalise_title("Cancer: A New Hope!") == normalise_title("cancer a new hope")


# --- de-duplication --------------------------------------------------------

def test_deduplicate_by_url():
    items = [
        make("Story one", "https://e.com/a"),
        make("Story one (syndicated)", "https://e.com/a?utm_medium=email"),
    ]
    assert len(deduplicate(items)) == 1


def test_deduplicate_by_title_across_sources():
    items = [
        make("Vaccine trial succeeds", "https://a.com/1"),
        make("Vaccine Trial Succeeds!", "https://b.com/9"),
    ]
    assert len(deduplicate(items)) == 1


def test_deduplicate_keeps_the_first_occurrence():
    items = [make("Same", "https://e.com/first"), make("Same", "https://e.com/second")]
    assert deduplicate(items)[0].url == "https://e.com/first"


def test_deduplicate_leaves_distinct_articles_alone():
    items = [make("One", "https://e.com/1"), make("Two", "https://e.com/2")]
    assert len(deduplicate(items)) == 2


def test_deduplicate_on_the_fixture_page(sample_html, sample_source):
    parsed = parse_articles(sample_html, sample_source)
    assert len(deduplicate(parsed)) == len(parsed) - 1  # one seeded duplicate


# --- keyword filtering -----------------------------------------------------

def test_filter_matches_titles_case_insensitively():
    items = [make("New CANCER drug approved", "https://e.com/1"), make("Football results", "https://e.com/2")]
    assert [a.title for a in filter_by_keywords(items, ["cancer"])] == ["New CANCER drug approved"]


def test_filter_matches_summaries_too():
    items = [make("Weekly roundup", "https://e.com/1", summary="Includes a vaccine update.")]
    assert len(filter_by_keywords(items, ["vaccine"])) == 1


def test_titles_only_mode_ignores_the_summary():
    items = [make("Weekly roundup", "https://e.com/1", summary="Includes a vaccine update.")]
    assert filter_by_keywords(items, ["vaccine"], search_summary=False) == []


def test_word_boundaries_prevent_substring_matches():
    items = [make("Influence of diet on mood", "https://e.com/1")]
    assert filter_by_keywords(items, ["flu"]) == []


def test_multi_word_keywords_match_as_a_phrase():
    items = [
        make("Heart disease risk falls", "https://e.com/1"),
        make("Disease of the heart valve", "https://e.com/2"),
    ]
    kept = filter_by_keywords(items, ["heart disease"])
    assert [a.url for a in kept] == ["https://e.com/1"]


def test_no_keywords_means_no_filtering():
    items = [make("Anything", "https://e.com/1")]
    assert filter_by_keywords(items, []) == items


def test_regex_characters_in_keywords_are_escaped():
    items = [make("A c++ study", "https://e.com/1")]
    assert filter_by_keywords(items, ["c++"]) == items  # must not raise


def test_matched_keywords_reports_each_hit():
    article = make("Vaccine and cancer research", "https://e.com/1")
    assert sorted(matched_keywords(article, ["vaccine", "cancer", "stroke"])) == ["cancer", "vaccine"]
