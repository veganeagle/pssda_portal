# PSSDA Portal

A Flask app for analyzing Ontario public-sector salary disclosure data —
DuckDB queries running directly over parquet files, no separate database.
This is the **beginning** of an analytics suite; right now it has one
working feature (a filtered year-panel comparison between two arbitrary
filter sets). If you're picking this up to build out the rest, read
**[ANALYTICS_SUITE_BRIEF.md](ANALYTICS_SUITE_BRIEF.md)** — it has the goal,
what exists, and what's still open.

## Where the data comes from

This project does not ingest or compute anything — it only reads
`data/processed/*.parquet`, which are copied snapshots of the output of a
separate pipeline project: **`pssda_pipeline`**. If the data here looks
stale (check `data/processed/employment_history_enriched.parquet`'s latest
`Year`), refresh it by re-copying from there:

```
employees_enriched.parquet, employment_history_enriched.parquet,
sectors_canonical.parquet
  ← pssda_pipeline/data/processed/
employer/employers_canonical.parquet
  ← pssda_pipeline/data/processed/employer/
```

Then regenerate the dropdown cache (see below) — it's derived from
`BASELINE_YEAR` in `web_app/config.py`, which also needs updating to match.
See `pssda_pipeline/README.md` for what every column in those files means.

## Setup

```
pip install -r requirements.txt
```

## Running it

```
python -m web_app.services.generate_dropdowns   # builds data/processed/dropdowns/*.json — run once, and again whenever the data or BASELINE_YEAR changes
python -m web_app.app                             # from the project root; http://127.0.0.1:5000
```

`GET /health` reports row counts for each dropdown cache — a quick way to
confirm the app started against real data.

## Architecture

```
web_app/
  app.py            — entry point (python -m web_app.app)
  __init__.py        — Flask app factory, registers blueprints
  config.py          — BASELINE_YEAR, YEARS_WINDOW, COLUMN_MAP (filter whitelist)
  db.py               — opens an in-memory DuckDB, registers one view per
                         parquet file in data/processed/ (+ employers_canonical)
  views/
    ui.py             — HTML routes (/compare_live)
    api.py            — JSON routes for cascading dropdowns (/api/employers, /api/titles, /api/regions)
  services/
    analytics_service.py   — build_panel_query(): the core analytical query
    dropdown_service.py    — loads/filters the dropdown cache
    generate_dropdowns.py  — (re)builds the dropdown cache from the parquet data
  templates/compare_live.html
```

**`db.py`** re-scans `data/processed/` for `*.parquet` at import time and
registers a DuckDB view named after each file (so `employment_history_enriched.parquet`
becomes queryable as `employment_history_enriched`). Add a new parquet file
there and it's automatically queryable — no code change needed to expose it.

**`analytics_service.py::build_panel_query(filters, years, names=False)`**
is the one real query in the app today: given a dict of filters and a list
of years, it returns a year-by-year panel (headcount, avg salary,
avg raise for returning employees, % female, employer count, etc.) from
`employment_history_enriched` joined to `employees_enriched`.

### Security pattern — follow this for any new query

Filter values are passed as DuckDB query parameters (`?` placeholders +
a params list to `db.query(sql, params)`), **not** interpolated into the SQL
string. Filter *keys* are checked against `COLUMN_MAP` in `config.py` — a
column name can't be parameterized in SQL, so anything not in that whitelist
is silently dropped rather than turned into a raw column reference. Any new
endpoint that builds SQL from request data needs to follow both rules.
(This wasn't true of the version this was ported from — see the migration
history in `pssda2025`'s git log if you want the details of what broke.)

There is deliberately no "run arbitrary SQL" endpoint. Don't add one without
real auth in front of it.

## Current features

- `GET /compare_live` — the dashboard: pick a sector/employer/region/job
  title for a baseline and a comparison, submit, get a side-by-side panel
  (headcount, salary, raises, benefits, % female) for `YEARS_RANGE`
  (currently the 3 years ending at `BASELINE_YEAR`, both from `config.py`).
- Cascading dropdowns: selecting a sector narrows the employer list;
  selecting an employer narrows the title list. Backed by a precomputed
  JSON cache (`data/processed/dropdowns/`), not a live query, for speed —
  regenerate it after any data refresh.
