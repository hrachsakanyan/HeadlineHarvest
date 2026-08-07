"""Source definitions: where to scrape and which CSS selectors to use.

Keeping selectors in a JSON file (instead of hard-coding them) means adapting to
a site redesign is a config edit, not a code change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES_FILE = PROJECT_ROOT / "config" / "sources.json"
DEFAULT_KEYWORDS_FILE = PROJECT_ROOT / "config" / "keywords_medical.txt"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

#: Sent on every request so site owners can identify (and contact) the crawler.
DEFAULT_USER_AGENT = (
    "HeadlineHarvestBot/1.0 (educational news scraper; "
    "+https://github.com/yourname/headlineharvest)"
)


class ConfigError(Exception):
    """Raised when a sources file is missing, malformed, or incomplete."""


@dataclass
class Source:
    """One page to scrape, plus the selectors that describe its markup."""

    name: str
    url: str
    item_selector: str
    title_selector: str
    link_selector: str = ""          # defaults to title_selector
    link_attr: str = "href"
    date_selector: str = ""
    date_attr: str = ""              # e.g. "datetime" on a <time> element
    summary_selector: str = ""
    delay: float | None = None       # per-source override, seconds
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.link_selector:
            self.link_selector = self.title_selector

    @classmethod
    def from_dict(cls, raw: dict) -> "Source":
        required = ("name", "url", "item_selector", "title_selector")
        missing = [key for key in required if not raw.get(key)]
        if missing:
            label = raw.get("name") or raw.get("url") or "<unnamed source>"
            raise ConfigError(f"Source {label!r} is missing: {', '.join(missing)}")

        known = {f for f in cls.__dataclass_fields__}
        unknown = set(raw) - known
        if unknown:
            raise ConfigError(
                f"Source {raw['name']!r} has unknown key(s): {', '.join(sorted(unknown))}"
            )
        return cls(**raw)


def load_sources(path: Path | str = DEFAULT_SOURCES_FILE) -> list[Source]:
    """Read and validate the sources file."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Sources file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Sources file {path} is not valid JSON: {exc}") from exc

    entries = raw.get("sources") if isinstance(raw, dict) else raw
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path} must contain a non-empty 'sources' list")

    return [Source.from_dict(entry) for entry in entries]


def load_keywords(path: Path | str = DEFAULT_KEYWORDS_FILE) -> list[str]:
    """Read a keyword file: one term per line, ``#`` starts a comment."""
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ConfigError(f"Keyword file not found: {path}") from exc

    keywords = []
    for line in lines:
        term = line.split("#", 1)[0].strip()
        if term:
            keywords.append(term)
    return keywords
