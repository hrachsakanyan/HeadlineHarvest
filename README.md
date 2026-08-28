# 🌾 HeadlineHarvest

### A polite, configurable news headline scraper for clean CSV & JSON datasets

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python\&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-100%20passing-brightgreen)](#tests)
[![License](https://img.shields.io/badge/license-MIT-yellow)](#license)
[![Scraping](https://img.shields.io/badge/scraping-robots.txt%20compliant-success)](#ethical-scraping)

**HeadlineHarvest** is a configurable news scraper that collects headlines from multiple sources, filters them by keyword, and exports a clean dataset as **CSV or JSON**.

> 🩺 Originally built around a medical-news use case, with keywords covering cardiology, oncology, vaccines, clinical trials and related topics. The scraper itself is completely domain-independent.

---

## ✨ Why HeadlineHarvest? 

The interesting part of a scraper isn't `requests.get()`.

It's everything around it:

* respecting `robots.txt`
* backing off when a server struggles
* handling missing dates
* resolving relative URLs
* dealing with broken text encoding
* de-duplicating articles
* filtering meaningful headlines
* producing valid CSV even when titles contain commas or newlines

**That's what this project is about.**

---

## 🚀 Features

### Core

| Feature                        | Description                                                                        |
| ------------------------------ | ---------------------------------------------------------------------------------- |
| 🌐 **HTTP Fetching**           | Fetches pages with a self-identifying User-Agent and per-request timeout           |
| 🎯 **CSS Parsing**             | Parses title, link, date and summary using CSS selectors                           |
| 🧹 **Graceful Missing Fields** | Missing fields become empty strings; items without a title or link are skipped     |
| 🔗 **URL Resolution**          | Relative links are automatically converted to absolute URLs                        |
| 📅 **Date Normalisation**      | Dates are normalised to `YYYY-MM-DD` while preserving the original text            |
| ⏱️ **Polite Delays**           | Adds delays between requests with jitter                                           |
| 📄 **CSV Export**              | Produces UTF-8 CSV that safely handles commas, quotes, newlines and non-ASCII text |

### Beyond the Basics

* 🤖 **`robots.txt` compliance**, including `Crawl-delay`
* ⚙️ **Multiple sources** configured through JSON — no code changes required
* ♻️ **De-duplication** across sources by canonical URL and normalised title
* 🔎 **Keyword filtering** with whole-word matching and multi-word phrases
* 🗂️ **JSON output** alongside or instead of CSV
* 🔁 **Retries with exponential backoff** for timeouts and 5xx responses
* 🧬 **Text repair** for real-world encoding problems
* 🧪 **100 offline tests** — the test suite never touches the network

---

## 🛠️ Tech Stack

| Technology        | Purpose              |
| ----------------- | -------------------- |
| **Python 3.9+**   | Core application     |
| **Requests**      | HTTP requests        |
| **CSS Selectors** | HTML parsing         |
| **JSON**          | Source configuration |
| **CSV / JSON**    | Data export          |
| **Pytest**        | Offline test suite   |

---

## 🌍 Target Sites & Legality

The bundled `config/sources.json` ships with:

| Source                                                                                 | Status     | Why                                     |
| -------------------------------------------------------------------------------------- | ---------- | --------------------------------------- |
| [ScienceDaily — Health & Medicine](https://www.sciencedaily.com/news/health_medicine/) | 🟢 Enabled | `robots.txt` disallows only `/test/`    |
| [ScienceDaily — Mind & Brain](https://www.sciencedaily.com/news/mind_brain/)           | 🟢 Enabled | Same host, second section               |
| [Hacker News](https://news.ycombinator.com/)                                           | ⚪ Disabled | Allowed, but asks for `Crawl-delay: 30` |

Hacker News is included as a worked example of a second layout and is left disabled so that a default run isn't spent sleeping.

Enable it with:

```bash
python -m src.main --source "Hacker News"
```

The scraper will honour the full **30-second delay**.

### ⚖️ Legality Note

This scraper reads publicly accessible pages, obeys `robots.txt`, identifies itself, and requests each page at most once per run.

Its behaviour is intended to be that of a **well-mannered client**, not a data-harvesting operation.

It stores:

* headlines
* links
* short summaries

This is enough to **point at an article**, not to republish it.

> Article text remains the publisher's copyright.

Before adding a source, read both its:

1. `robots.txt`
2. Terms of Service

These are separate things. A `robots.txt` file permitting a crawl does **not** by itself grant you rights to the content.

Some sites forbid automated access in their terms even where `robots.txt` is silent.

---

## 📦 Setup 

### Requirements

**Python 3.9+**

### 1. Clone the repository

```bash
git clone https://github.com/yourname/headlineharvest.git
cd headlineharvest
```

### 2. Create a virtual environment

#### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

For the test suite:

```bash
pip install -r requirements-dev.txt
```

---

## ▶️ Usage

Run the scraper as a module from the project root.

### Scrape everything from enabled sources

Exports to a timestamped CSV:

```bash
python -m src.main
```

### Medical headlines as CSV + JSON

```bash
python -m src.main \
  --keywords config/keywords_medical.txt \
  --format both
```

### Custom keywords + limit

```bash
python -m src.main \
  --keyword cardiology \
  --keyword vaccine \
  --limit 10 \
  --output data/output/cardio.csv
```

### Scrape one source with debug logging 

```bash
python -m src.main \
  --source "Mind & Brain" \
  --verbose
```

---

## 🧰 Command-Line Options

| Option                     | Default                  | Description                                        |
| -------------------------- | ------------------------ | -------------------------------------------------- |
| `--sources FILE`           | `config/sources.json`    | Site definitions to load                           |
| `--source NAME`            | all enabled              | Only sources matching this substring; repeatable   |
| `--keywords FILE`          | none                     | Keyword file to filter by                          |
| `--keyword TERM`           | none                     | Extra keyword; repeatable                          |
| `--titles-only`            | off                      | Match keywords against titles instead of summaries |
| `--format {csv,json,both}` | `csv`                    | Output format                                      |
| `--output-dir DIR`         | `data/output/`           | Directory for timestamped files                    |
| `--output PATH`            | —                        | Exact output path; extension determines format     |
| `--limit N`                | —                        | Keep at most N articles                            |
| `--no-dedupe`              | off                      | Keep duplicate headlines                           |
| `--delay SECONDS`          | `2.0`                    | Pause between requests                             |
| `--timeout SECONDS`        | `15.0`                   | Per-request timeout                                |
| `--retries N`              | `2`                      | Retries for timeouts and 5xx responses             |
| `--user-agent UA`          | `HeadlineHarvestBot/1.0` | User-Agent header                                  |
| `-v` / `-q`                | —                        | Debug logging / warnings only                      |

> **Important:** `--delay` is a floor, not a ceiling. If `robots.txt` asks for a longer `Crawl-delay`, the longer value wins.

---

## 🚦 Exit Codes

|  Code | Meaning                                |
| ----: | -------------------------------------- |
|   `0` | Success                                |
|   `1` | Nothing left to export after filtering |
|   `2` | Configuration error                    |
| `130` | Interrupted                            |

---

## 📊 Sample Run

```text
$ python -m src.main --keywords config/keywords_medical.txt --limit 5

INFO     Fetching ScienceDaily - Health & Medicine
         (https://www.sciencedaily.com/news/health_medicine/)

INFO     ScienceDaily - Health & Medicine: found 22 article(s)

INFO     Fetching ScienceDaily - Mind & Brain
         (https://www.sciencedaily.com/news/mind_brain/)

INFO     ScienceDaily - Mind & Brain: found 22 article(s)

INFO     Removed 6 duplicate article(s)

INFO     Keyword filter kept 17 of 38 article(s)

Scraped 44 headline(s) from 2 source(s).

Exported 5 after de-duplication and filtering:
  -> data/output/headlines_20260803_231552.csv
```

---

## 📄 Sample Output

Generated file:

```text
data/output/headlines_20260803_231552.csv
```

Example:

```csv
title,url,published,published_raw,summary,source,scraped_at
A Simple Supplement Could Help the Immune System Fight Cancer and Viruses,https://www.sciencedaily.com/releases/2026/08/260802223417.htm,2026-08-03,"Aug. 3, 2026","Low arginine levels may allow cancer cells and viruses to slip past the immune system by reducing production of a crucial cellular warning protein. In mice, arginine-rich diets led to fewer colon tumors ...",ScienceDaily - Health & Medicine,2026-08-03T19:15:48+00:00
"This Once-a-week Workout May Help Cut Belly Fat, Study Shows",https://www.sciencedaily.com/releases/2026/08/260801042831.htm,2026-08-02,"Aug. 2, 2026","A surprisingly small dose of exercise may deliver major health benefits for adults carrying excess fat around the waist. In a four-month trial involving 315 adults ...",ScienceDaily - Health & Medicine,2026-08-03T19:15:48+00:00
```

### Output Columns

| Column          | Description                                     |
| --------------- | ----------------------------------------------- |
| `title`         | Headline text                                   |
| `url`           | Absolute link to the article                    |
| `published`     | Normalised `YYYY-MM-DD`, empty when unparseable |
| `published_raw` | Exactly what the page said, e.g. `Aug. 3, 2026` |
| `summary`       | Teaser text, date prefix removed                |
| `source`        | Which configured source it came from            |
| `scraped_at`    | UTC timestamp of the run                        |

Both date columns are kept on purpose:

* `published` is what you sort and filter on
* `published_raw` lets you debug a site whose format changed

---

## ➕ Adding a New Source

No code changes are required.

Simply add an entry to:

```text
config/sources.json
```

Example:

```json
{
  "name": "Example Health News",
  "url": "https://example.com/health/",
  "item_selector": "article.story",
  "title_selector": "h2 a",
  "link_selector": "h2 a",
  "link_attr": "href",
  "date_selector": "time",
  "date_attr": "datetime",
  "summary_selector": "p.teaser",
  "delay": 2.0,
  "enabled": true
}
```

### How selectors work

`item_selector` picks each headline block.

Every other selector is applied **inside that block**.

Omit a selector, or set it to `""`, when a site does not publish that field. The resulting column will simply be empty.

### Finding CSS selectors

Open the target page:

```text
Right-click a headline
        ↓
     Inspect
        ↓
Find the repeating wrapper
        ↓
Identify the relevant classes/elements
```

Only these fields are required:

* `name`
* `url`
* `item_selector`
* `title_selector`

Unknown keys are rejected during configuration loading.

For example, a typo such as:

```text
titel_selector
```

fails loudly instead of silently producing empty columns.

---

# 🤝 Ethical Scraping

HeadlineHarvest is intentionally designed to behave politely toward the sites it accesses.

### 1. Read `robots.txt` first

Handled in [`src/robots.py`](src/robots.py) according to RFC 9309.

* `404` → no rules, everything is allowed
* `401` / `403` → rules are off-limits, so the site is considered off-limits
* `5xx` / network failure → status is unknown and the scraper fails closed rather than guessing

### 2. Honour `Crawl-delay`

If a site asks for 30 seconds, it gets 30 seconds — even if `--delay` is lower.

### 3. Identify yourself

The default User-Agent identifies the bot and where it can be found, allowing an administrator to see who is visiting.

### 4. Ask once

The scraper makes one request per page per run, with a delay between requests.

There is no parallel hammering.

### 5. Back off instead of retrying blindly

* `5xx` → exponential-backoff retry
* timeout → exponential-backoff retry
* `404` → no retry
* `403` → no retry

### 6. Take metadata, not content

HeadlineHarvest collects:

* headlines
* links
* teasers

That's enough to build an index, not a copy.

### 7. Test offline

Every test runs against saved HTML in:

```text
tests/fixtures/
```

A test suite that hits live websites would be slower, flakier and less polite.

---

## 🧪 Tests

Run the complete test suite:

```bash
python -m pytest
```

Expected:

```text
100 tests, ~0.5s, no network
```

For verbose output:

```bash
python -m pytest -v
```

### Test Coverage

| File                     | Covers                                                              |
| ------------------------ | ------------------------------------------------------------------- |
| `tests/test_scraper.py`  | Parsing, missing fields, date normalisation, text cleaning, retries |
| `tests/test_filters.py`  | URL canonicalisation, de-duplication, keyword matching              |
| `tests/test_exporter.py` | CSV escaping, encoding, JSON shape                                  |
| `tests/test_robots.py`   | Allow/disallow, `Crawl-delay`, error statuses, caching              |
| `tests/test_config.py`   | Configuration validation and error messages                         |
| `tests/test_pipeline.py` | End-to-end CLI runs against fixture HTML                            |

---

## 🧠 Notes from the Real Web

Two problems this project encountered that most tutorial pages don't show you.

### Character Encoding

ScienceDaily serves:

```text
Content-Type: text/html
```

without specifying a charset.

As a result, `requests` falls back to ISO-8859-1 and can mangle curly apostrophes.

The solution is to sniff the body encoding whenever the header doesn't specify one.

### Dirty Data

The same pages contain the byte sequence:

```text
\xc2\x97
```

This is a Windows-1252 em dash that was double-encoded into UTF-8.

It arrives as the control character:

```text
U+0097
```

It's invisible, `strip()` doesn't remove it, and it can silently end up inside the CSV.

`clean_text()` in [`src/scraper.py`](src/scraper.py):

* maps the affected range back through `cp1252`
* removes zero-width characters

---

## 🗂️ Project Structure

```text
headlineharvest/
│
├── src/
│   ├── main.py          # CLI: argument parsing, wiring, output
│   ├── scraper.py       # fetching, parsing, text cleaning, delays
│   ├── exporter.py      # CSV and JSON writers
│   ├── filters.py       # de-duplication and keyword filtering
│   ├── robots.py        # robots.txt compliance
│   ├── config.py        # source definitions and validation
│   └── models.py        # the Article dataclass
│
├── config/
│   ├── sources.json             # sites and their CSS selectors
│   └── keywords_medical.txt     # default keyword list
│
├── data/
│   └── output/                  # generated datasets (gitignored)
│
├── tests/
│   ├── fixtures/                # saved HTML, so tests stay offline
│   └── test_*.py
│
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

---

## 🔮 Possible Next Steps

The project can be extended with:

* 📅 **Scheduling** — run automatically every day using cron / Task Scheduler
* 🗄️ **SQLite persistence** — append to a database instead of creating a new file for every run
* 🔗 **Article metadata extraction** — follow each link to retrieve the full article date and author
* 📡 **RSS / Atom support** — use feeds where available because they're cheaper and friendlier than HTML scraping

---

## 📜 License

**MIT License**

See [`LICENSE`](LICENSE).

> The license covers this code, **not the content of any site you point it at.**

---

<div align="center">

### 🌾 HeadlineHarvest

**Collect headlines. Respect websites. Build clean datasets.**

Made with Python · Built for practical web scraping · Designed to be polite

</div>
