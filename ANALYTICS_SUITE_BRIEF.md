# Brief: Where the Analytics Suite Stands

Handoff document for whoever (human or a fresh Claude Code session) picks this
up next. Read `README.md` first for the architecture and how to run it — this
doc is status and open questions, not a reference.

## The goal

A portal for **deep, longitudinal analysis** of Ontario public-sector salary
data. Explicitly **not** a casual individual-lookup site (see `SUNSHINE.md`'s
note on this, and the "Top Earners" position-filter design — free-text title
search was tried and reverted because it mixed unrelated roles across
domains). The three original goals, and where each stands:

1. **Salary trends for specific jobs, over time.** Done — the position page's
   Trend table and the combo (employer+position) page's Trend table both
   cover the full 2010–2025 history, with median/P90 bands, not just an
   average.
2. **Annual increase (raise) analysis.** Done, and done carefully — every
   raise figure in the app is a matched-cohort average (same person, same
   exact position, in both years), never a same-role year-over-year average
   of two different populations. See `SUNSHINE.md` #2 and
   `pipeline/matched_cohort.py`.
3. **Comparisons between similar entities.** Partially done. Positions are
   already scoped to `(sector, title_norm)` as the safe comparable unit
   (raw title alone spans unrelated domains — e.g. a police "Inspector" vs. a
   health-unit "Inspector"). What's *not* built: an explicit "find peer
   employers" feature using `Population` or `SubSector` (both already sit in
   `employer_wide`/`employers_canonical`, just unused for this) — e.g. "show
   me municipalities within 20% of this one's population." Nobody's designed
   what "similar" should mean yet; that's a real open design question, not
   an implementation gap.

## What exists

Five page types (employee, employer, position, the employer+position "combo"
drill-down, and a province-wide top-earners leaderboard), each backed by its
own precomputed cube — see `README.md`'s Pages and Cubes tables for the full
list. Worth calling out specifically since they're easy to miss:

- **The combo page** (`/employer/<id>/position/<sector>/<title>`) is reachable
  only as a second step from an employer's or position's table (a small "⤢"
  link per row), never searched directly. Both directions land on the same
  page.
- **`Title_Norm` label/breakdown fix.** Aggregating by `Title_Norm` is
  necessary (many employers don't share a finer split — see the TDSB
  Teacher/Principal case in `SUNSHINE.md`-adjacent commit history), but
  showing an aggregate group's label used to pick one arbitrary raw title
  variant, which actively misled (a merged Elementary+Secondary group
  displayed as if it were Elementary-only). Fixed: the label is always the
  generic `Title_Norm`, with a real composition breakdown
  (`pipeline/title_breakdown.py`) shown alongside — variants get named
  individually only when they're ≥10% of the group and ≥5 people, otherwise
  folded into "Other."
- **No charts yet.** All trend data is tabular. The one visual element is a
  reused `.pbar` bar (originally built for the employee payband percentile,
  since reused for nothing else yet) — genuinely no JS charting, no SVG
  plotting. A scatter plot (headcount × salary across *all* roles at an
  employer, for outlier-spotting) was discussed and deliberately deferred,
  not forgotten.

## What's genuinely still open

- **No home/landing page.** `/` redirects straight to employee search.
  There's a real nav bar (Employees / Employers / Positions / Top Earners)
  but no actual front door with framing, stats, or orientation for a first-
  time visitor.
- **Charts** (see above) — the scatter plot specifically, and possibly a
  proper line chart for the trend tables instead of/alongside the raw table.
- **"Similar employers" peer-grouping**, per goal 3 above — needs a design
  conversation before building (same-size-tier? same-subsector? some
  combination?), same open question the very first version of this brief
  raised and never resolved.
- **Monetization tier** — discussed early (API access, bulk export, custom
  benchmarking reports were the leading ideas), nothing built. Everything
  live today is free-tier.
- **A known upstream data-quality bug, not ours to fix here**:
  `Title_Norm="ADMINISTRATION"` (at least at TDSB) conflates genuinely
  different roles spanning a $101K Finance Support Officer to a $236K CEO —
  a normalization-dictionary problem in `pssda_pipeline`, not something
  fixable from this repo. The composition breakdown (above) makes it
  visible rather than hidden, but doesn't correct it.

## Data gotchas — read `SUNSHINE.md` before writing a new aggregation

Every non-obvious field meaning, the three methodology rules
(new-entrant-≠-new-hire, matched-cohort raises, mid-year-move/leave
ambiguity), and the `Title_Norm` grouping rationale are documented there, not
repeated here. The short version: several `employment_history_enriched`
columns look self-explanatory and aren't (`TenureOnList`, `GapFlag`,
`YoYSalaryIncrease`'s `0.0` sentinel) — get this wrong and a chart looks fine
but asserts something false.
