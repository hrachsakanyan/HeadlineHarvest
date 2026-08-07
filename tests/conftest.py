"""Shared pytest fixtures.

Every test runs offline against the saved HTML in ``tests/fixtures`` - a test
suite that hits the live internet is slow, flaky, and rude to the site owner.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the project root importable so ``from src...`` works without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Source  # noqa: E402
from src.models import Article  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_html() -> str:
    return (FIXTURES / "sample_news.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_source() -> Source:
    return Source(
        name="Fixture News",
        url="https://example.com/news/health/",
        item_selector="#heroes .col-md-6, #featured_blurbs .tab-pane",
        title_selector=".latest-head a",
        date_selector=".story-date",
        summary_selector=".latest-summary",
    )


@pytest.fixture
def articles() -> list[Article]:
    return [
        Article(
            title="Vaccine trial reports strong results",
            url="https://example.org/a",
            published="2026-07-31",
            published_raw="July 31, 2026",
            summary="A phase III clinical trial met its endpoint.",
            source="Fixture News",
        ),
        Article(
            title="Quantum computing milestone reached",
            url="https://example.org/b",
            summary="A new record in qubit coherence time.",
            source="Fixture News",
        ),
    ]
