"""robots.txt handling - the rules that keep the scraper welcome."""

from __future__ import annotations

import requests

from src.robots import RobotsPolicy

ROBOTS = """
User-agent: *
Crawl-delay: 5
Disallow: /private/
Disallow: /admin

User-agent: BadBot
Disallow: /
"""


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Serves robots.txt per host and counts how often it was asked."""

    def __init__(self, response):
        self.response = response
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def policy(response, user_agent="HeadlineHarvestBot/1.0"):
    return RobotsPolicy(FakeSession(response), user_agent)


def test_allowed_path():
    assert policy(FakeResponse(text=ROBOTS)).can_fetch("https://e.com/news/health/") is True


def test_disallowed_path():
    assert policy(FakeResponse(text=ROBOTS)).can_fetch("https://e.com/private/x") is False


def test_disallowed_prefix_without_trailing_slash():
    assert policy(FakeResponse(text=ROBOTS)).can_fetch("https://e.com/admin/users") is False


def test_crawl_delay_is_read():
    assert policy(FakeResponse(text=ROBOTS)).crawl_delay("https://e.com/news/") == 5.0


def test_missing_robots_txt_allows_everything():
    assert policy(FakeResponse(status_code=404)).can_fetch("https://e.com/anything") is True


def test_forbidden_robots_txt_blocks_everything():
    # 401/403 on robots.txt means "you may not read the rules" -> stay out.
    assert policy(FakeResponse(status_code=403)).can_fetch("https://e.com/anything") is False


def test_server_error_blocks_everything():
    # Fail closed: a 5xx is a temporary unknown, not permission to crawl.
    assert policy(FakeResponse(status_code=503)).can_fetch("https://e.com/anything") is False


def test_network_failure_blocks_everything():
    assert policy(requests.ConnectionError("no route")).can_fetch("https://e.com/x") is False


def test_crawl_delay_is_none_when_the_site_is_blocked():
    assert policy(FakeResponse(status_code=503)).crawl_delay("https://e.com/x") is None


def test_robots_txt_is_fetched_once_per_host():
    session = FakeSession(FakeResponse(text=ROBOTS))
    rules = RobotsPolicy(session, "HeadlineHarvestBot/1.0")

    rules.can_fetch("https://e.com/a")
    rules.can_fetch("https://e.com/b")
    rules.crawl_delay("https://e.com/c")
    assert session.calls == 1

    rules.can_fetch("https://other.com/a")
    assert session.calls == 2
