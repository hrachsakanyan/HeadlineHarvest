"""Data structures shared across the scraper."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

#: Column order used by both the CSV and the JSON exporter.
FIELDNAMES = [
    "title",
    "url",
    "published",
    "published_raw",
    "summary",
    "source",
    "scraped_at",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Article:
    """A single scraped headline.

    Only ``title`` and ``url`` are required; every other field may legitimately
    be missing on a given site, in which case it stays an empty string rather
    than ``None`` so the CSV row keeps its shape.
    """

    title: str
    url: str
    published: str = ""       # normalised to YYYY-MM-DD when we can parse it
    published_raw: str = ""   # exactly what the page said, e.g. "Aug. 3, 2026"
    summary: str = ""
    source: str = ""
    scraped_at: str = field(default_factory=_utc_now)

    @property
    def missing_fields(self) -> list[str]:
        """Names of the optional fields that came back empty."""
        return [name for name in FIELDNAMES if not getattr(self, name)]

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
