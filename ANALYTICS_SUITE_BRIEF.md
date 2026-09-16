# Brief: Building Out the Analytics Suite

This is a handoff document for whoever (human or a fresh Claude Code
session) picks up this project next. It has no memory of the conversation
that produced this codebase — read this first.

## The goal

A portal for **deep, longitudinal analysis** of Ontario public-sector
salary data. In the owner's own words, explicitly **not** individual
employee lookup, but:

1. Salary trends for specific jobs, over time.
2. Annual increase (raise) analysis.
3. Comparisons between entities that are similar.

## What already exists — don't rebuild this

- A working Flask app (`web_app/`) with DuckDB running directly over
  parquet files — no ETL, no separate database to keep in sync.
- One real analytical query, `analytics_service.py::build_panel_query()`:
  given filters + a list of years, returns a year-by-year panel (headcount,
  avg salary, avg raise for returning employees, % female, benefits,
  employer count).
- One page, `/compare_live`: pick filters for a baseline and a comparison
  group, get both panels side by side with deltas.
- Cascading sector → employer → title dropdowns, backed by a precomputed
  JSON cache.
- A parameterized-query + column-whitelist pattern for safely building SQL
  from user filters — **follow this pattern for anything new**; see
  README.md's "Security pattern" section.

Read `README.md` for the architecture and how to run it before touching
anything.

## What's genuinely missing — this is the actual work

**1. Trends over the full available history.** The data covers
**2010–2025** (16 years), but `build_panel_query()` and the UI only ever
show a fixed short window (`YEARS_RANGE` in `config.py`, currently the 3
years ending at `BASELINE_YEAR`). "Salary trends for specific jobs" and
"annual increases" really call for a full-history view — a line chart of
avg salary / avg raise over all 16 years for a chosen job title, sector, or
employer, not a 3-column table. This is probably the most direct gap
between what exists and the stated goal, and the data already supports it —
`YoYSalaryIncrease` is precomputed per employee-year, so a proper multi-year
trend query is mostly "don't filter years down to a window."

**2. A real notion of "similar entities."** Right now, `/compare_live` lets
you compare *any* two arbitrary filter sets — there's no structure around
what makes two employers comparable. The data has real material to build
this from:
   - `SubSector` (in `employment_history_enriched`) — e.g. compare all
     `Catholic_Board` school boards to each other, or all `Municipal`
     employers, rather than one arbitrary pair. Only populated for 5 of the
     ~11 sectors (Crown Agencies, Healthcare, Municipalities, Other Public
     Service, School Boards) — see `pssda_pipeline/README.md`'s
     "Known limitations."
   - `Population` (in `employers_canonical.parquet`, for municipal
     employers) — a natural basis for peer-grouping by size (compare
     mid-size cities to mid-size cities, not to Toronto).
   - `Region`/`GeographicArea` — geographic peer grouping.

   This needs a design conversation with the owner before building — "similar" could mean same subsector, same size tier, same geography, or some combination, and the right answer probably depends on which comparison (job trend vs. employer benchmarking) is being made.

**3. Visualization.** The current output is an HTML table. "Deep,
longitudinal analysis" of trends over 16 years is a much better fit for
charts (a line per entity/title over years) than a table. No charting
library is wired in yet.

## Data you'll actually be querying

`employment_history_enriched` (one row per employee-year) is where almost
everything above comes from. Relevant fields for this work specifically:
`Year`, `SalaryPaid`, `TotalComp`, `YoYSalaryIncrease`, `TenureOnList`,
`SectorID`, `EmployerID`/`EmployerName`, `Title_Norm`/`Rank_Norm`,
`SubSector`. Full column-by-column meaning (including real gotchas — e.g.
`TenureOnList` is years-since-first-seen, not consecutive years; a `0.0` in
`YoYSalaryIncrease` can mean "no prior year to compare," not "no raise") is
in `pssda_pipeline/README.md`. Read it before writing queries against these
fields — several of them look self-explanatory and aren't.

Two limitations worth knowing before designing a job-title trend feature:
job title normalization (`Title_Norm`, needed to group "the same job" across
employers/years) matches ~65–75% of rows — long-tail unique titles won't
have it. Decide up front whether the trend feature should fall back to raw
`JobTitleNorm` text matching for uncovered titles, or accept the gap.

## Suggested starting point

Talk to the owner about priority before building — but if a default is
needed, extending `build_panel_query()` (or adding a sibling function) to
return the full multi-year series for a single filtered entity/title, and
rendering it as a line chart, is the smallest step that visibly moves
toward "longitudinal" and doesn't require resolving the "similar entities"
design question first.
