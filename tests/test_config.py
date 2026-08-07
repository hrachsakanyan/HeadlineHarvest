"""Loading and validating the sources / keywords configuration."""

from __future__ import annotations

import json

import pytest

from src.config import (
    DEFAULT_KEYWORDS_FILE,
    DEFAULT_SOURCES_FILE,
    ConfigError,
    Source,
    load_keywords,
    load_sources,
)
from src.main import gather_keywords, select_sources


def write_sources(tmp_path, sources):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": sources}), encoding="utf-8")
    return path


VALID = {
    "name": "Test Source",
    "url": "https://e.com/news/",
    "item_selector": "li.item",
    "title_selector": "a.title",
}


# --- the configuration that ships with the project -------------------------

def test_bundled_sources_file_is_valid():
    sources = load_sources(DEFAULT_SOURCES_FILE)
    assert sources
    assert all(s.url.startswith("https://") for s in sources)


def test_bundled_keyword_file_loads():
    keywords = load_keywords(DEFAULT_KEYWORDS_FILE)
    assert "cardiology" in keywords
    assert "vaccine" in keywords
    assert not any(k.startswith("#") for k in keywords)


# --- validation ------------------------------------------------------------

def test_missing_required_field_is_reported(tmp_path):
    broken = {k: v for k, v in VALID.items() if k != "title_selector"}
    with pytest.raises(ConfigError, match="title_selector"):
        load_sources(write_sources(tmp_path, [broken]))


def test_unknown_key_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="titel_selector"):
        load_sources(write_sources(tmp_path, [{**VALID, "titel_selector": "a"}]))


def test_malformed_json_is_reported(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="valid JSON"):
        load_sources(path)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_sources(tmp_path / "nope.json")


def test_empty_source_list_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="non-empty"):
        load_sources(write_sources(tmp_path, []))


# --- keyword files ---------------------------------------------------------

def test_comments_and_blank_lines_are_ignored(tmp_path):
    path = tmp_path / "kw.txt"
    path.write_text("# heading\n\ncancer\nvaccine  # inline comment\n", encoding="utf-8")
    assert load_keywords(path) == ["cancer", "vaccine"]


def test_gather_keywords_merges_file_and_inline(tmp_path):
    path = tmp_path / "kw.txt"
    path.write_text("cancer\n", encoding="utf-8")

    args = type("Args", (), {"keywords": path, "inline_keywords": ["stroke"]})()
    assert gather_keywords(args) == ["cancer", "stroke"]


# --- --source selection ----------------------------------------------------

def sources():
    return [
        Source(name="Alpha News", url="https://a.com", item_selector="li", title_selector="a"),
        Source(name="Beta Health", url="https://b.com", item_selector="li", title_selector="a",
               enabled=False),
    ]


def test_no_filter_returns_everything():
    assert len(select_sources(sources(), None)) == 2


def test_filter_matches_a_case_insensitive_substring():
    assert [s.name for s in select_sources(sources(), ["beta"])] == ["Beta Health"]


def test_explicit_selection_re_enables_a_disabled_source():
    assert select_sources(sources(), ["beta"])[0].enabled is True


def test_unmatched_filter_raises_and_lists_the_options():
    with pytest.raises(ConfigError, match="Alpha News"):
        select_sources(sources(), ["gamma"])
