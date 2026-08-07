"""End-to-end runs, with the network replaced by the saved fixture page."""

from __future__ import annotations

import csv
import json

import pytest

from src import main as cli
from src import scraper
from src.robots import RobotsPolicy


class StubRobots:
    """Stands in for RobotsPolicy without touching the network."""

    def __init__(self, allowed=True, delay=None):
        self.allowed = allowed
        self.delay = delay

    def can_fetch(self, url):
        return self.allowed

    def crawl_delay(self, url):
        return self.delay


@pytest.fixture(autouse=True)
def no_real_sleeping(monkeypatch):
    """Politeness delays are correct behaviour, but tests should not wait."""
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)


# --- scrape_source ---------------------------------------------------------

def test_scrape_source_returns_articles(monkeypatch, sample_html, sample_source):
    monkeypatch.setattr(scraper, "fetch_page", lambda *a, **k: sample_html)
    articles = scraper.scrape_source(sample_source, session=None, robots=StubRobots())
    assert len(articles) == 6


def test_scrape_source_obeys_a_disallow(monkeypatch, sample_source):
    def explode(*args, **kwargs):
        raise AssertionError("fetch_page must not be called for a disallowed URL")

    monkeypatch.setattr(scraper, "fetch_page", explode)
    assert scraper.scrape_source(sample_source, session=None, robots=StubRobots(allowed=False)) == []


def test_a_longer_crawl_delay_from_robots_wins(monkeypatch, sample_html, sample_source):
    slept = []
    monkeypatch.setattr(scraper, "fetch_page", lambda *a, **k: sample_html)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: slept.append(seconds))

    sample_source.delay = 2.0
    scraper.scrape_source(sample_source, session=None, robots=StubRobots(delay=30.0))
    assert slept and slept[0] >= 30.0


def test_our_delay_wins_when_it_is_the_longer_one(monkeypatch, sample_html, sample_source):
    slept = []
    monkeypatch.setattr(scraper, "fetch_page", lambda *a, **k: sample_html)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: slept.append(seconds))

    sample_source.delay = 10.0
    scraper.scrape_source(sample_source, session=None, robots=StubRobots(delay=1.0))
    assert slept and 10.0 <= slept[0] < 11.0


def test_a_failing_source_does_not_abort_the_run(monkeypatch, sample_source):
    def fail(*args, **kwargs):
        raise scraper.FetchError("boom")

    monkeypatch.setattr(scraper, "fetch_page", fail)
    assert scraper.scrape_source(sample_source, session=None, robots=StubRobots()) == []


def test_disabled_sources_are_skipped(monkeypatch, sample_html, sample_source):
    monkeypatch.setattr(scraper, "fetch_page", lambda *a, **k: sample_html)
    sample_source.enabled = False
    assert scraper.scrape_sources([sample_source], session=None, robots=StubRobots()) == []


# --- the CLI, end to end ---------------------------------------------------

@pytest.fixture
def offline_cli(monkeypatch, sample_html, tmp_path):
    """Point the CLI at a one-source config served from the fixture HTML."""
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Fixture News",
                        "url": "https://example.com/news/health/",
                        "item_selector": "#heroes .col-md-6, #featured_blurbs .tab-pane",
                        "title_selector": ".latest-head a",
                        "date_selector": ".story-date",
                        "summary_selector": ".latest-summary",
                        "delay": 0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(scraper, "fetch_page", lambda *a, **k: sample_html)
    monkeypatch.setattr(cli, "build_session", lambda ua: DummySession())
    monkeypatch.setattr(cli, "RobotsPolicy", lambda *a, **k: StubRobots())
    return config


class DummySession:
    def close(self):
        pass


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_cli_writes_a_csv(offline_cli, tmp_path):
    out = tmp_path / "out.csv"
    assert cli.main(["--sources", str(offline_cli), "--output", str(out), "--quiet"]) == 0

    rows = read_csv(out)
    assert len(rows) == 5  # 6 parsed, minus the seeded duplicate
    assert all(row["title"] and row["url"] for row in rows)


def test_cli_keyword_filter(offline_cli, tmp_path):
    out = tmp_path / "out.csv"
    cli.main([
        "--sources", str(offline_cli), "--output", str(out),
        "--keyword", "cancer", "--keyword", "vaccine", "--quiet",
    ])

    titles = [row["title"] for row in read_csv(out)]
    assert len(titles) == 2
    assert not any("Quantum" in title for title in titles)


def test_cli_no_dedupe_keeps_the_duplicate(offline_cli, tmp_path):
    out = tmp_path / "out.csv"
    cli.main(["--sources", str(offline_cli), "--output", str(out), "--no-dedupe", "--quiet"])
    assert len(read_csv(out)) == 6


def test_cli_limit(offline_cli, tmp_path):
    out = tmp_path / "out.csv"
    cli.main(["--sources", str(offline_cli), "--output", str(out), "--limit", "2", "--quiet"])
    assert len(read_csv(out)) == 2


def test_cli_writes_both_formats(offline_cli, tmp_path):
    outdir = tmp_path / "out"
    cli.main([
        "--sources", str(offline_cli), "--output-dir", str(outdir),
        "--format", "both", "--quiet",
    ])
    assert len(list(outdir.glob("*.csv"))) == 1
    assert len(list(outdir.glob("*.json"))) == 1


def test_cli_reports_when_nothing_matches(offline_cli, tmp_path):
    out = tmp_path / "out.csv"
    code = cli.main([
        "--sources", str(offline_cli), "--output", str(out),
        "--keyword", "zzzznotarealword", "--quiet",
    ])
    assert code == 1
    assert not out.exists()


def test_cli_reports_a_bad_config(tmp_path):
    assert cli.main(["--sources", str(tmp_path / "missing.json"), "--quiet"]) == 2


def test_cli_reports_an_unknown_source_name(offline_cli):
    assert cli.main(["--sources", str(offline_cli), "--source", "nope", "--quiet"]) == 2


def test_robots_policy_is_the_real_class_by_default():
    # Guards against a stub leaking out of a fixture into the shipped CLI.
    assert cli.RobotsPolicy is RobotsPolicy
