"""CSV and JSON export."""

from __future__ import annotations

import csv
import json

from src.exporter import export_csv, export_json, timestamped_path
from src.models import FIELDNAMES, Article


def test_csv_has_a_header_and_one_row_per_article(tmp_path, articles):
    path = export_csv(articles, tmp_path / "out.csv")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0]) == FIELDNAMES
    assert len(rows) == 2
    assert rows[0]["title"] == "Vaccine trial reports strong results"


def test_csv_writes_empty_strings_for_missing_fields(tmp_path, articles):
    path = export_csv(articles, tmp_path / "out.csv")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[1]["published"] == ""
    assert rows[1]["published_raw"] == ""


def test_csv_survives_commas_quotes_and_newlines(tmp_path):
    messy = Article(
        title='He said "hello", then left\nand returned',
        url="https://e.com/1",
        summary="a, b, c",
    )
    path = export_csv([messy], tmp_path / "out.csv")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["title"] == messy.title
    assert len(rows) == 1


def test_csv_keeps_non_ascii_characters(tmp_path):
    article = Article(title="Հետազոտություն — 研究 – café", url="https://e.com/1")
    path = export_csv([article], tmp_path / "out.csv")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        assert list(csv.DictReader(handle))[0]["title"] == article.title


def test_csv_does_not_double_space_rows_on_windows(tmp_path, articles):
    path = export_csv(articles, tmp_path / "out.csv")
    assert b"\r\r\n" not in path.read_bytes()


def test_empty_result_still_writes_a_header(tmp_path):
    path = export_csv([], tmp_path / "out.csv")
    assert path.read_text(encoding="utf-8-sig").strip() == ",".join(FIELDNAMES)


def test_json_payload_shape(tmp_path, articles):
    path = export_json(articles, tmp_path / "out.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["count"] == 2
    assert len(payload["articles"]) == 2
    assert set(payload["articles"][0]) == set(FIELDNAMES)
    assert "generated_at" in payload


def test_json_keeps_non_ascii_unescaped(tmp_path):
    path = export_json([Article(title="café", url="https://e.com/1")], tmp_path / "out.json")
    assert "café" in path.read_text(encoding="utf-8")


def test_export_creates_missing_directories(tmp_path, articles):
    path = export_csv(articles, tmp_path / "deep" / "nested" / "out.csv")
    assert path.exists()


def test_timestamped_path_shape(tmp_path):
    path = timestamped_path(tmp_path, "csv")
    assert path.suffix == ".csv"
    assert path.name.startswith("headlines_")
    assert path.parent == tmp_path
