# HeadlineHarvest

A polite news scraper that collects headlines from configurable sources, filters
them by keyword, and exports a clean dataset as CSV or JSON.

It was built around a medical-news use case — the bundled keyword list covers
cardiology, oncology, vaccines, clinical trials and friends — but nothing in the
code is domain-specific. Point it at other sources and swap the keyword file.

The interesting part of a scraper is not `requests.get()`. It is everything
around it: obeying `robots.txt`, backing off when a server struggles, coping with
headlines that are missing a date, and not writing broken CSV when a title
contains a comma. That is what this project is about.

---

## Features

**Core**

- Fetches pages with a self-identifying User-Agent and a per-request timeout
- Parses title, link, date and summary with CSS selectors
- Missing fields degrade to empty strings; items with no title *or* no link are
  skipped rather than exported as junk
- Relative links (`/releases/2026/08/x.htm`) are resolved to absolute URLs
- Dates are normalised to `YYYY-MM-DD`, with the original text kept alongside
- Polite delays between requests, with jitter
- Exports UTF-8 CSV that survives commas, quotes, newlines and non-ASCII text

**Beyond the basics**

- **robots.txt compliance**, including `Crawl-delay` — see [Ethics](#ethical-scraping)
- **Multiple sources** defined in JSON, no code changes needed
- **De-duplication** across sources, by canonical URL *and* by normalised title
- **Keyword filtering** with whole-word matching and multi-word phrases
- **JSON output** alongside (or instead of) CSV
- **Retries with exponential backoff** for timeouts and 5xx responses
- **Text repair** for real-world encoding damage (see [Notes](#notes-from-the-real-web))
- 100 offline tests — the suite never touches the network

---

## Target sites and legality

The bundled `config/sources.json` ships with:

| Source | Status | Why |
|---|---|---|
| [ScienceDaily — Health & Medicine](https://www.sciencedaily.com/news/health_medicine/) | enabled | `robots.txt` disallows only `/test/` |
| [ScienceDaily — Mind & Brain](https://www.sciencedaily.com/news/mind_brain/) | enabled | same host, second section |
| [Hacker News](https://news.ycombinator.com/) | **disabled** | allowed, but asks for `Crawl-delay: 30` |

Hacker News is included as a worked example of a second layout, and left disabled
so a default run is not spent sleeping. Enable it with
`--source "Hacker News"` and the scraper will honour the full 30-second delay.

**Legality note.** This scraper reads publicly accessible pages, obeys
`robots.txt`, identifies itself, and requests each page at most once per run — the
behaviour of a well-mannered client, not a data-harvesting operation. It stores
headlines, links and short summaries, which is enough to *point at* an article,
not to republish it. Article text remains the publisher's copyright.

Before adding a source, read its `robots.txt` **and** its terms of service — the
two are separate things, and `robots.txt` permitting a crawl does not by itself
grant you rights to the content. Some sites forbid automated access in their
terms even where `robots.txt` is silent.

---

## Setup

Requires Python 3.9+.

```bash
git clone https://github.com/yourname/headlineharvest.git
cd headlineharvest

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

For the test suite: `pip install -r requirements-dev.txt`

---

## Usage

Run it as a module from the project root:

```bash
# Everything from the enabled sources, to a timestamped CSV
python -m src.main

# Medical headlines only, as CSV and JSON
python -m src.main --keywords config/keywords_medical.txt --format both

# Ad-hoc keywords, top 10, to a specific file
python -m src.main --keyword cardiology --keyword vaccine --limit 10 --output data/output/cardio.csv

# One source, with debug logging
python -m src.main --source "Mind & Brain" --verbose
```

### Options

| Option | Default | What it does |
|---|---|---|
| `--sources FILE` | `config/sources.json` | Site definitions to load |
| `--source NAME` | all enabled | Only sources matching this substring (repeatable) |
| `--keywords FILE` | none | Keyword file to filter by |
| `--keyword TERM` | none | Extra keyword (repeatable) |
| `--titles-only` | off | Match keywords against titles, not summaries |
| `--format {csv,json,both}` | `csv` | Output format |
| `--output-dir DIR` | `data/output/` | Where timestamped files are written |
| `--output PATH` | — | Exact output path; extension picks the format |
| `--limit N` | — | Keep at most N articles |
| `--no-dedupe` | off | Keep duplicate headlines |
| `--delay SECONDS` | `2.0` | Pause between requests |
| `--timeout SECONDS` | `15.0` | Per-request timeout |
| `--retries N` | `2` | Retries for timeouts and 5xx |
| `--user-agent UA` | `HeadlineHarvestBot/1.0` | User-Agent header |
| `-v` / `-q` | — | Debug logging / warnings only |

`--delay` is a floor, not a ceiling: if `robots.txt` asks for a longer
`Crawl-delay`, the longer value wins.

### Exit codes

`0` success · `1` nothing left to export after filtering · `2` configuration
error · `130` interrupted.

---

## Sample output

```
$ python -m src.main --keywords config/keywords_medical.txt --limit 5
INFO     Fetching ScienceDaily - Health & Medicine (https://www.sciencedaily.com/news/health_medicine/)
INFO     ScienceDaily - Health & Medicine: found 22 article(s)
INFO     Fetching ScienceDaily - Mind & Brain (https://www.sciencedaily.com/news/mind_brain/)
INFO     ScienceDaily - Mind & Brain: found 22 article(s)
INFO     Removed 6 duplicate article(s)
INFO     Keyword filter kept 17 of 38 article(s)

Scraped 44 headline(s) from 2 source(s).
Exported 5 after de-duplication and filtering:
  -> data/output/headlines_20260803_231552.csv
```

`data/output/headlines_20260803_231552.csv`:

```csv
title,url,published,published_raw,summary,source,scraped_at
A Simple Supplement Could Help the Immune System Fight Cancer and Viruses,https://www.sciencedaily.com/releases/2026/08/260802223417.htm,2026-08-03,"Aug. 3, 2026","Low arginine levels may allow cancer cells and viruses to slip past the immune system by reducing production of a crucial cellular warning protein. In mice, arginine-rich diets led to fewer colon tumors ...",ScienceDaily - Health & Medicine,2026-08-03T19:15:48+00:00
"This Once-a-week Workout May Help Cut Belly Fat, Study Shows",https://www.sciencedaily.com/releases/2026/08/260801042831.htm,2026-08-02,"Aug. 2, 2026","A surprisingly small dose of exercise may deliver major health benefits for adults carrying excess fat around the waist. In a four-month trial involving 315 adults ...",ScienceDaily - Health & Medicine,2026-08-03T19:15:48+00:00
```

| Column | Notes |
|---|---|
| `title` | Headline text |
| `url` | Absolute link to the article |
| `published` | Normalised `YYYY-MM-DD`, empty when unparseable |
| `published_raw` | Exactly what the page said, e.g. `Aug. 3, 2026` |
| `summary` | Teaser text, date prefix removed |
| `source` | Which configured source it came from |
| `scraped_at` | UTC timestamp of the run |

Both date columns are kept on purpose: `published` is what you sort and filter
on, `published_raw` is what lets you debug a site whose format changed.

---

## Adding a source

No code required — add an entry to `config/sources.json`:

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

`item_selector` picks each headline block; every other selector is applied
*inside* that block. Omit a selector (or set it to `""`) when a site does not
publish that field — the column will simply be empty.

To find selectors: open the page, right-click a headline → *Inspect*, and look
for the repeating wrapper element and the classes on it.

Only `name`, `url`, `item_selector` and `title_selector` are required; unknown
keys are rejected at load time so a typo like `titel_selector` fails loudly
instead of silently producing empty columns.

---

## Ethical scraping

The rules this project follows, and why:

1. **Read `robots.txt` first, and cache it.** Handled in [src/robots.py](src/robots.py)
   per RFC 9309: `404` means no rules and everything is allowed; `401`/`403` mean
   the rules are off-limits, so the site is too; `5xx` or a network failure means
   *unknown*, and the scraper fails closed rather than guessing.
2. **Honour `Crawl-delay`.** If a site asks for 30 seconds, it gets 30 seconds,
   even when `--delay` is lower.
3. **Identify yourself.** The default User-Agent names the bot and where to find
   it, so an administrator can see who is visiting.
4. **Ask once.** One request per page per run, with a delay in between. No
   parallel hammering.
5. **Back off, don't retry blindly.** A 5xx or timeout is retried with
   exponential backoff; a 404 or 403 is not retried at all.
6. **Take metadata, not content.** Headlines, links and teasers — enough to build
   an index, not a copy.
7. **Test offline.** Every test runs against saved HTML in `tests/fixtures/`.
   A test suite that hits a live site is slow, flaky, and rude.

---

## Notes from the real web

Two things this project ran into that no tutorial page will show you:

**Encoding.** ScienceDaily serves `Content-Type: text/html` with no charset, so
`requests` falls back to ISO-8859-1 and mangles every curly apostrophe. The fix
is to sniff the body encoding whenever the header omits one.

**Dirty data.** The same pages contain the byte sequence `\xc2\x97` — a
Windows-1252 em dash that was double-encoded into UTF-8, arriving as the control
character U+0097. It is invisible, `strip()` will not remove it, and it lands
silently in the CSV. `clean_text()` in [src/scraper.py](src/scraper.py) maps that
range back through cp1252 and drops the zero-width characters too.

---

## Tests

```bash
python -m pytest            # 100 tests, ~0.5s, no network
python -m pytest -v         # per-test names
```

| File | Covers |
|---|---|
| [tests/test_scraper.py](tests/test_scraper.py) | Parsing, missing fields, date normalisation, text cleaning, retries |
| [tests/test_filters.py](tests/test_filters.py) | URL canonicalisation, de-duplication, keyword matching |
| [tests/test_exporter.py](tests/test_exporter.py) | CSV escaping, encoding, JSON shape |
| [tests/test_robots.py](tests/test_robots.py) | Allow/disallow, `Crawl-delay`, error statuses, caching |
| [tests/test_config.py](tests/test_config.py) | Config validation and error messages |
| [tests/test_pipeline.py](tests/test_pipeline.py) | End-to-end CLI runs against fixture HTML |

---

## Project structure

```
headlineharvest/
├── src/
│   ├── main.py          # CLI: argument parsing, wiring, output
│   ├── scraper.py       # fetching, parsing, text cleaning, delays
│   ├── exporter.py      # CSV and JSON writers
│   ├── filters.py       # de-duplication and keyword filtering
│   ├── robots.py        # robots.txt compliance
│   ├── config.py        # source definitions and validation
│   └── models.py        # the Article dataclass
├── config/
│   ├── sources.json           # sites and their CSS selectors
│   └── keywords_medical.txt   # default keyword list
├── data/output/         # generated datasets (gitignored)
├── tests/
│   ├── fixtures/        # saved HTML, so tests stay offline
│   └── test_*.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

---

## Possible next steps

- Scheduling, so a run happens daily without a human (cron / Task Scheduler)
- Appending to a SQLite database instead of a new file per run, so the dataset
  accumulates and duplicates are caught across runs
- Following each link to pull the full article date and author
- An RSS/Atom parser for sources that publish feeds — cheaper and friendlier
  than scraping HTML

---

## License

MIT — see [LICENSE](LICENSE). Note that the license covers this code, not the
content of any site you point it at.
