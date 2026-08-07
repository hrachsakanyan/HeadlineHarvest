"""Command-line entry point.

    python -m src.main --keywords config/keywords_medical.txt --format both
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import (
    DEFAULT_KEYWORDS_FILE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SOURCES_FILE,
    DEFAULT_USER_AGENT,
    ConfigError,
    Source,
    load_keywords,
    load_sources,
)
from .exporter import export_csv, export_json, timestamped_path
from .filters import deduplicate, filter_by_keywords
from .models import Article
from .robots import RobotsPolicy
from .scraper import build_session, scrape_sources

logger = logging.getLogger("headlineharvest")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="headlineharvest",
        description="Scrape news headlines into a CSV/JSON dataset, politely.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES_FILE,
                        help="JSON file describing the sites to scrape")
    parser.add_argument("--source", dest="only", action="append", metavar="NAME",
                        help="Scrape only this source (repeatable, case-insensitive substring)")

    parser.add_argument("--keywords", type=Path, metavar="FILE",
                        help=f"Keyword file to filter by (try {DEFAULT_KEYWORDS_FILE.name})")
    parser.add_argument("--keyword", dest="inline_keywords", action="append", metavar="TERM",
                        help="Extra keyword to filter by (repeatable)")
    parser.add_argument("--titles-only", action="store_true",
                        help="Match keywords against titles only, not summaries")

    parser.add_argument("--format", choices=("csv", "json", "both"), default="csv",
                        help="Output format")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Where to write the dataset")
    parser.add_argument("--output", type=Path, metavar="PATH",
                        help="Exact output path (overrides --output-dir; implies one format)")
    parser.add_argument("--limit", type=int, metavar="N",
                        help="Keep at most N articles")
    parser.add_argument("--no-dedupe", action="store_true",
                        help="Keep duplicate headlines")

    parser.add_argument("--delay", type=float, default=2.0, metavar="SECONDS",
                        help="Pause between requests (robots.txt Crawl-delay wins if longer)")
    parser.add_argument("--timeout", type=float, default=15.0, metavar="SECONDS",
                        help="Per-request timeout")
    parser.add_argument("--retries", type=int, default=2,
                        help="Retries for timeouts and 5xx responses")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                        help="User-Agent sent with every request")

    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug logging")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only show warnings and errors")
    return parser


def configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)-8s %(message)s", stream=sys.stderr)


def select_sources(sources: list[Source], wanted: list[str] | None) -> list[Source]:
    """Apply ``--source`` filters; without them, every enabled source is used."""
    if not wanted:
        return sources

    needles = [w.lower() for w in wanted]
    chosen = [s for s in sources if any(n in s.name.lower() for n in needles)]
    if not chosen:
        available = ", ".join(s.name for s in sources)
        raise ConfigError(f"No source matched {wanted!r}. Available: {available}")

    for source in chosen:
        source.enabled = True  # an explicit request overrides "enabled": false
    return chosen


def gather_keywords(args: argparse.Namespace) -> list[str]:
    keywords: list[str] = []
    if args.keywords:
        keywords.extend(load_keywords(args.keywords))
    if args.inline_keywords:
        keywords.extend(args.inline_keywords)
    return keywords


def write_output(articles: list[Article], args: argparse.Namespace) -> list[Path]:
    written: list[Path] = []

    if args.output:
        suffix = args.output.suffix.lower()
        if suffix == ".json":
            written.append(export_json(articles, args.output))
        else:
            written.append(export_csv(articles, args.output))
        return written

    if args.format in ("csv", "both"):
        written.append(export_csv(articles, timestamped_path(args.output_dir, "csv")))
    if args.format in ("json", "both"):
        written.append(export_json(articles, timestamped_path(args.output_dir, "json")))
    return written


def run(args: argparse.Namespace) -> int:
    sources = select_sources(load_sources(args.sources), args.only)
    active = [source for source in sources if source.enabled]
    if not active:
        logger.error("Every source in %s is disabled - nothing to do", args.sources)
        return 2
    keywords = gather_keywords(args)

    session = build_session(args.user_agent)
    robots = RobotsPolicy(session, args.user_agent, timeout=args.timeout)

    try:
        articles = scrape_sources(
            active,
            session,
            robots,
            default_delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
        )
    finally:
        session.close()

    scraped_count = len(articles)
    if not args.no_dedupe:
        articles = deduplicate(articles)
    if keywords:
        articles = filter_by_keywords(articles, keywords, search_summary=not args.titles_only)
    if args.limit:
        articles = articles[: args.limit]

    if not articles:
        logger.warning("Nothing to export (scraped %s article(s) before filtering)", scraped_count)
        return 1

    paths = write_output(articles, args)

    print(f"\nScraped {scraped_count} headline(s) from {len(active)} source(s).")
    print(f"Exported {len(articles)} after de-duplication and filtering:")
    for path in paths:
        print(f"  -> {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose, args.quiet)
    try:
        return run(args)
    except ConfigError as exc:
        logger.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
