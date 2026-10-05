# OPSCI.ca — Ontario Public Sector Compensation Insights

A research/benchmarking tool over 16 years (2010–2025) of Ontario public-sector
salary disclosure data — entity-resolved employees, employers, and normalized
job titles, with longitudinal trends, matched-cohort raise analysis, and
cross-employer peer comparison. See **[SUNSHINE.md](SUNSHINE.md)** for what the
underlying disclosure is and the methodology rules that follow from it (read
this before writing any new aggregation — it covers real gotchas like "new
entrant" not meaning "new hire"). See
**[ANALYTICS_SUITE_BRIEF.md](ANALYTICS_SUITE_BRIEF.md)** for what's built vs.
still open if you're picking this up fresh.

## Architecture

Three layers, each with one job, each independently runnable:

```
pipeline/    dev-time only. Reads data/processed/*.parquet (source, handed off
             from the separate pssda_pipeline project), computes aggregates in
             pandas, writes flat parquet tables to data/profiles/. Never runs
             as part of the live app.

access/      always-on. DuckDB views over data/profiles/*.parquet only — never
             touches data/processed. One module per cube, each exposing typed
             lookup/search functions that return Pydantic models. This is the
             only place SQL gets written.

web_app/     Flask, one blueprint per entity type. Views call access/, never
             DuckDB or parquet directly. Templates only format already-final
             numbers — no math in Jinja.

models/      Pydantic schemas shared by pipeline (defines what a cube's output
             columns must be) and access (what a lookup returns).
```

**Why this split**: `pipeline/` can use pandas or DuckDB, whichever's more
convenient per cube — it doesn't matter, because `access/` never reads from
`pipeline/`'s code, only from its *output* (the parquet files). This means the
web app's data-access pattern and its security guarantees don't change no
matter what pipeline implementation changes underneath.

### Security pattern

Every `access/*.py` query uses `?` bound parameters for user-supplied values.
The only place a variable is spliced into raw SQL text is a column-name
whitelist drawn from a fixed in-code tuple (never from `request.args`) — see
`access/employee_search.py`. There is no "run arbitrary SQL" endpoint.
`LIKE` wildcards (`%`, `_`) are escaped in every `contains`-style filter.

The web app also runs a global per-IP request throttle
(`web_app/rate_limit.py`, 300 requests/hour, single-process in-memory) — not a
security boundary (the underlying data is already public), just an
availability guard against one source hammering the app. `debug` mode is off
by default in `web_app/app.py` (Werkzeug's debugger is a real RCE risk if ever
exposed beyond localhost) — opt in locally with `PSSDA_DEBUG=1`.

## Where the source data comes from

This project does not ingest or entity-resolve anything itself — `pipeline/`
only reads `data/processed/*.parquet`, which are copied snapshots of the
output of a separate project, **`pssda_pipeline`**. If the data looks stale
(check `employment_history_enriched.parquet`'s latest `Year`), refresh by
re-copying from there:

```
employees_enriched.parquet, employment_history_enriched.parquet,
sectors_canonical.parquet
  ← pssda_pipeline/data/processed/
employer/employers_canonical.parquet
  ← pssda_pipeline/data/processed/employer/
```

See `pssda_pipeline/README.md` for what every source column means — several
look self-explanatory and aren't (`TenureOnList`, `GapFlag`,
`YoYSalaryIncrease`'s `0.0` sentinel — also covered in `SUNSHINE.md`).

## Setup

```
pip install -r requirements.txt
```

## Running it

```
python -m pipeline.cubes.employee_profile --full     # ~671K employees, ~50s
python -m pipeline.cubes.employer_profile             # ~3,500 employers, ~15s
python -m pipeline.cubes.position_profile             # ~1,100 positions, ~15s
python -m pipeline.cubes.employer_position_profile    # ~5,000 combos, ~15s
python -m pipeline.cubes.top_earners                  # every year, ~16s
python -m pipeline.cubes.notable_roles                 # current-year civic/leadership roles, ~5s
python -m web_app.app                                  # http://127.0.0.1:5000
```

Run the cube builds once, and again whenever `data/processed/` is refreshed
with a new year's data. `data/profiles/index.json` records when each cube was
last built. Each `pipeline/cubes/*.py` is runnable standalone and independent
of the others — no cube reads another cube's output. `employee_profile.py`
without `--full` builds a small hand-picked test set instead (exercises every
code path: a resolved title, a gap year, an employer switch, an unresolved
title) — useful for iterating on the pipeline without a 50-second full build.

Every `access/*.py` and most `pipeline/cubes/*.py` modules have a
`if __name__ == "__main__"` smoke test — e.g. `python -m access.employer_profile`
round-trips a few real records through the Pydantic models and asserts valid
JSON. Run these after any pipeline or model change.

`GET /health` returns `{"status": "ok"}` — confirms the app started.

## Production (opsci.ca)

One Hetzner Cloud VM, `opsci-prod` (CX23, Falkenstein, Ubuntu 26.04, 2.28.102.159).
DNS is a Hetzner DNS zone; WHC is the registrar only (nameservers point to
Hetzner). Admin access is SSH as root with a key only (password login off).

```
/srv/opsci/app        git clone of this repo (owned by the `opsci` system user)
/srv/opsci/app/data   profiles/ (copied, not in git) and visits.txt (runtime)
/srv/opsci/venv       Python venv from requirements.txt (pinned)
/etc/systemd/system/opsci.service   gunicorn: 1 worker, 8 threads, 127.0.0.1:8000
/etc/caddy/Caddyfile  HTTPS, www -> apex redirect, security headers, no access log
```

One gunicorn worker on purpose: the rate limiter, export limiter and visit
counter are single-process. gunicorn must stay bound to 127.0.0.1 — ProxyFix
trusts exactly one proxy hop (Caddy).

**Deploy a code change** (after pushing to GitHub):
```
ssh root@2.28.102.159 'sudo -u opsci git -C /srv/opsci/app pull && systemctl restart opsci'
```
If requirements.txt changed, also run
`/srv/opsci/venv/bin/pip install -r /srv/opsci/app/requirements.txt` before the restart.

**Refresh the data** (after rebuilding cubes locally), from the repo root:
```
tar cf - -C data profiles | ssh root@2.28.102.159 'tar xf - -C /srv/opsci/app/data && chown -R opsci:opsci /srv/opsci/app/data && systemctl restart opsci'
```

Logs: `journalctl -u opsci` (service events and errors only — no access logs
are kept, per the Privacy page). Search-engine indexing policy lives in
`web_app/seo.py`; `robots.txt`, `sitemap.xml` and `llms.txt` are served by
`web_app/views/pages.py`.

## Pages

| Route | What it shows |
|---|---|
| `/` | Home dashboard — the "all Ontario" landing page: province trend chart, sector payroll-mix donut, fastest movers, largest employers, top disclosed earners preview, a curated "Ontario's highest paid..." notable-roles grid, and a top-15-roles table. A sector picker jumps to the matching `/sector/<id>` page. |
| `/sector/<id>` | One of the 11 real sectors, modeled on the home dashboard but a standalone template (not homologated with it) — same shape of cards (trend, fastest movers, a role-mix donut, largest employers, top earners preview), plus a 6-card "highest paid normalized positions" grid (always distinct roles, floor of 5 incumbents, pinned to the sector's own current year) and a "top 15 roles in {sector}" table. |
| `/search` | Employee search — name, sector, employer-contains, title-contains, year-present. Requires at least one filter (no open browse of individuals). |
| `/employee/<id>` | One person: current role, peer-standing percentile (3 tiers), full disclosure history with YoY/gap/switch/promotion flags. |
| `/employers` | Employer search — name-contains, sector (auto-submits on change). Above the form: a dense "employers by sector" table (count, disclosed employees with an inline sparkline, median employer size, largest employer). No filter = top 50 by disclosed employees, with a "see all" escape hatch to the unfiltered list. |
| `/employer/<id>` | One employer: a disclosed-payroll-&-employees trend chart, top positions (by headcount, with median/P90 salary band and a real composition breakdown — see `SUNSHINE.md` on why that matters), full workforce history, top disclosed earners. |
| `/positions` | Position search — title-contains, sector (auto-submits on change). Above the form: a "positions by sector" table (disclosed employees with sparkline, count of distinct normalized positions, % of disclosed employees whose title actually normalized, most frequent role). Positions are keyed by `(sector, title_norm)`, never title alone (a bare title spans unrelated domains). |
| `/position/<sector_id>/<title_norm>` | One position, province-wide: trend over time, matched-cohort raise (not a naive year-average), leaderboard of every employer offering this role. |
| `/employer/<id>/position/<sector_id>/<title_norm>` | The "combo" page — one position at one specific employer. Reached only as a second step from an employer's or position's table, never searched directly: clicking a position/employer name in those tables drills into the combo (the contextually relevant destination), with a small "province-wide"/"overall" label alongside for the explicit escape hatch to the broader page. Both directions land on the same combo page. |
| `/top-earners` | Province-wide leaderboard, filterable by sector, employer-contains, and an exact position (live-filterable dropdown, not free text — see the position-filter JS for why free text was rejected: it mixed unrelated roles across sectors). |
| `/compare/employer?a=<id>&b=<id>` | Two employers, side by side: workforce/pay tables, a grouped year-by-year disclosed-employees bar chart, a most-common-roles table (matched by `title_norm` where both sides offer it, "not offered here" otherwise), and matched top earners. `a`/`b` need not share a sector — a sector picker on the page (defaulting to `a`'s sector, changeable) lets the right-hand side come from anywhere, e.g. a university vs. a college; roles/earners just degrade to "not offered here" when they don't overlap. |
| `/compare/position?sector=<id>&title=<title_norm>&a=<id>&b=<id>` | The same normalized position at two employers in the *same* sector (unlike employer-mode, this stays same-sector-only — `title_norm` is sector-keyed, so a cross-sector "match" would just be a coincidence of spelling, not a real comparable role). Workforce/pay tables, the same grouped bar chart, matched top earners. |

Every page's headcount/payroll language is standardized on "disclosed employees"/"disclosed payroll" (never bare "headcount"/"payroll", which would misleadingly suggest an employer's full workforce or budget) — one footnote in `base.html`'s footer, rendered site-wide, spells out the precise definition once, including that disclosed payroll is a sum of *salary only* (not total compensation).

## Cubes

All in `data/profiles/`, one manifest section each in `index.json`:

| Cube | Pipeline module | Key tables |
|---|---|---|
| `employee_profile` | `pipeline/cubes/employee_profile.py` | `employee_wide`, `employee_history`, `employee_payband_standing` |
| `employer_profile` | `pipeline/cubes/employer_profile.py` | `employer_wide`, `employer_history`, `employer_top_earners`, `employer_top_positions`, `employer_top_position_breakdown` |
| `position_profile` | `pipeline/cubes/position_profile.py` | `position_wide`, `position_history`, `position_by_employer` |
| `employer_position_profile` | `pipeline/cubes/employer_position_profile.py` | `employer_position_wide`, `employer_position_history`, `employer_position_breakdown` |
| `top_earners` | `pipeline/cubes/top_earners.py` | `top_earners_history` (every year, ranked within that year's own population — province/sector/employer/position rank + pool size precomputed) |
| `notable_roles` | `pipeline/cubes/notable_roles.py` | `notable_roles_current` (current year's highest-paid incumbent for a curated list of civic/institutional leadership roles — bypasses the usual 3-person minimum since these are legitimately singleton roles) |

Shared pipeline helpers (used across multiple cubes, not standalone cubes):
`pipeline/matched_cohort.py` (same-incumbent raise, per `SUNSHINE.md` #2),
`pipeline/gender.py` (aggregate-only, 20-person minimum), `pipeline/rankings.py`
(current-year province/sector/employer/position dense ranks),
`pipeline/title_breakdown.py` (which raw `JobTitleNorm` variants are large
enough within a `Title_Norm` group to name individually vs. fold into "Other").
