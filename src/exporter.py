"""Writing the collected articles to disk as CSV or JSON."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from .models import FIELDNAMES, Article

logger = logging.getLogger(__name__)


def timestamped_path(output_dir: Path | str, extension: str, prefix: str = "headlines") -> Path:
    """``data/output/headlines_20260803_142530.csv``"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(output_dir) / f"{prefix}_{stamp}.{extension.lstrip('.')}"


def _prepare(path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def export_csv(articles: list[Article], path: Path | str) -> Path:
    """Write a UTF-8 CSV.

    ``newline=""`` stops Windows from doubling the line endings, and the
    ``utf-8-sig`` BOM makes Excel display non-ASCII characters correctly.
    """
    path = _prepare(path)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for article in articles:
            writer.writerow(article.to_dict())

    logger.info("Wrote %s article(s) to %s", len(articles), path)
    return path


def export_json(articles: list[Article], path: Path | str) -> Path:
    """Write pretty-printed JSON with a small metadata header."""
    path = _prepare(path)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "count": len(articles),
        "articles": [article.to_dict() for article in articles],
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    logger.info("Wrote %s article(s) to %s", len(articles), path)
    return path
