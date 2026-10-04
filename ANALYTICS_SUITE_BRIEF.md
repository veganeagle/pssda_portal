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
   average. The home and sector dashboards add an actual SVG trend chart
   (bars=disclosed employees, line=disclosed payroll) on top of this.
2. **Annual increase (raise) analysis.** Done, and done carefully — every
   raise figure in the app is a matched-cohort average (same person, same
   exact position, in both years), never a same-role year-over-year average
   of two different populations. See `SUNSHINE.md` #2 and
   `pipeline/matched_cohort.py`.
3. **Comparisons between similar entities.** Mostly done. Positions are
   already scoped to `(sector, title_norm)` as the safe comparable unit
   (raw title alone spans unrelated domains — e.g. a police "Inspector" vs. a
   health-unit "Inspector"). The sector dashboards cover one layer of this
   (every sector vs. every other sector: trend, role mix, fastest movers,
   6-highest-paid). Direct side-by-side comparison is now built —
   `/compare/employer` and `/compare/position` (`access/comparison.py`,
   `web_app/views/compare.py`): two employers, or the same normalized
   position at two employers in the same sector. Employer-mode comparison is
   *not* restricted to one sector — a sector picker on the page (defaulting
   to the left-hand employer's own sector, changeable) lets the right-hand
   side come from anywhere, e.g. a university vs. a college; roles/earners
   that don't exist on one side just show "not offered here" rather than
   erroring. What's *still not* built: an explicit "find peer employers"
   feature using `Population`, `Region`, or `SubSector` (all already sit in
   `employer_wide`, just unused for peer-grouping) — e.g. "show me
   municipalities within 20% of this one's population." That's a
   recommendation/discovery feature (surfacing *which* employer to compare
   against), distinct from the comparison page itself (which now handles any
   two employers you already know you want to compare), and nobody's
   designed what "similar" should mean yet.

## What exists

**Pages** (see `README.md`'s Pages table for the full route list): a home
dashboard (`/`) and one dashboard per sector (`/sector/<id>`) sharing a
visual language but deliberately *not* the same template — home is the
standalone "all Ontario" landing page and may carry things (disclosures,
links) a sector page doesn't. Below those: employee, employer, position, the
employer+position "combo" drill-down, and a province-wide top-earners
leaderboard, each backed by its own precomputed cube.

- **Charts exist now.** `web_app/static/js/charts.js` has two reusable SVG
  renderers — `renderTrendChart` (dual-series: bars + line, used on home,
  every sector page, and the employer page) and `renderDonutChart` (used for
  sector payroll-mix on home and position-mix on sector pages). No charting
  library — hand-rolled SVG, no dependency. The scatter plot (headcount ×
  salary across all roles at an employer, for outlier-spotting) discussed
  early on is still deferred, not forgotten.
- **"By sector" overview tables** on `/employers` and `/positions`, above
  the search form: dense tables (not cards — a card-grid version was tried
  first and was "too dull"/took too much vertical space) with an inline
  sparkline on the main count column (`color-mix` over `--accent`, scaled to
  that column's own max) and a small per-sector color dot matching the donut
  palette. `/positions`'s version surfaces something genuinely useful: % of
  a sector's disclosed employees whose title actually normalized — Crown
  Agencies sits at ~20% mapped vs. Judiciary at ~99%, a real signal about
  where the title-normalization dictionary needs work.
- **Terminology is standardized site-wide.** "Headcount"/"payroll" and the
  inconsistent "Employees on List"/"on list" labels are now "disclosed
  employees"/"disclosed payroll" in prose, tiles, and chart legends, and the
  abbreviated "Disclosed Emp." in table headers. One footnote in
  `base.html`'s footer (rendered on every page) defines both precisely,
  including that disclosed payroll is a sum of *salary only*
  (`SalaryPaid`), not total compensation (`TotalComp` includes taxable
  benefits) — confirmed from `pipeline/cubes/employer_profile.py`'s own
  aggregation, not assumed.
- **Rebranded to OPSCI.ca** — "Ontario Public Sector Compensation Insights."
- **Side-by-side employer/position comparison** (`/compare/employer`,
  `/compare/position`) — workforce/pay tables (right-justified, employer
  names as links to the profile), a grouped year-by-year bar chart
  (disclosed employees, one pair of columns per year — replaced an earlier
  line-chart attempt that read as flat noise with two differently-scaled
  series on one axis), a most-common-roles table for employer-mode, and
  matched top earners. Entry points live on the employer and combo profile
  pages (`.compare-cta`, visually prominent by design) and on the comparison
  page itself (a smaller in-page picker to change the right-hand side
  without navigating back). Employer-mode's sector picker makes the
  right-hand side cross-sector-capable, per "The goal" #3 above.
- **Title-normalization dictionary gaps found via the comparison feature,
  fixed in `pssda_pipeline`**: "City Manager" wasn't mapped at all (Toronto's
  and Ottawa's City Manager showed as unmatched "not offered here" rows in a
  municipality-vs-municipality comparison — the exact-match variant existed
  in the dictionary but had a blank `Title_Norm`, i.e. reviewed but never
  finished). Also added "Director of Education" and "Associate Director"
  (School Boards sector) variant coverage, including "...AND TREASURER..."
  compounds mapped to the generic `TREASURER` role for consistency with an
  existing sibling convention. A reminder that dictionary coverage gaps are
  usually found this way — a feature that cross-references two employers'
  title lists surfaces a blank `Title_Norm` immediately, a single employer's
  own page doesn't.
- **`Title_Norm` label/breakdown fix.** Aggregating by `Title_Norm` is
  necessary (many employers don't share a finer split — see the TDSB
  Teacher/Principal case in `SUNSHINE.md`-adjacent commit history), but
  showing an aggregate group's label used to pick one arbitrary raw title
  variant, which actively misled (a merged Elementary+Secondary group
  displayed as if it were Elementary-only). Fixed: the label is always the
  generic `Title_Norm`. The per-variant composition breakdown
  (`pipeline/title_breakdown.py`) still exists and is still shown on the
  combo page's "Composition" panel, but was *removed* from the employer
  profile's "Top positions" table — it read as noise there, not signal.

## Known data-quality findings from this pass (not yet acted on)

- **Possible duplicate-entity split**: at least one example (Kevin Smith)
  where the same real person may have been entity-resolved into two
  separate `employee_id`s instead of one continuous record. Not yet
  systematically investigated — this is about the entity-resolution step
  upstream in `pssda_pipeline`, not something `pssda_portal` can fix itself,
  but the portal is where it's visible and where a report mechanism would
  live.
- **Possible retirement-year compensation inflation**: a hypothesis, not yet
  investigated — some of the very top entries in top-earners lists may be
  a final-year payout effect (e.g. banked sick time, severance, vacation
  payout bundled into that year's disclosed salary) rather than a genuinely
  representative salary. Worth a scoped look at whether top-of-list people
  disproportionately have `TenureOnList` ending that same year, but
  deliberately *not* prioritized yet (see the fresh plan below).

## Prioritized plan (as of this pass)

1. **Top Earners and Employee search parity** — bring both up to the
   Employers/Positions treatment: an info section above the search box,
   consistent terminology. Employee search has no natural aggregate the way
   the others do, so this one's worth a discuss-first like the sector pages
   got, not a straight copy of the pattern.
2. **Subsegment features** — the cheap part first: a `SubSector` donut and a
   `Region` breakdown on the sector pages that have the data (see below),
   reusing the donut component already built. `Region` specifically is the
   thing `SUNSHINE.md` names as a goal ("regional pay disparity analysis")
   and has never been surfaced anywhere in the UI. Once this lands, it's
   also the natural base for the still-open "find peer employers"
   recommendation feature noted under "The goal" #3 above.
3. **A user-facing correction/contact mechanism** — for reporting suspected
   entity-resolution errors (mis-merged or over-split people, e.g. the
   Kevin Smith case below) or other data issues. Doesn't exist in any form
   yet (no contact page, no report-a-problem link anywhere in the UI).
4. **A methodology/limitations page** — explain what "disclosed" means,
   known entity-resolution error modes, the title-normalization coverage
   gap, matched-cohort raise methodology, etc., in plain language for a
   visitor rather than scattered across `SUNSHINE.md` (a dev doc) and
   inline muted footnotes.
5. **Visual/UI polish pass** — deliberately after 1–4, so it's one coherent
   design pass over a fuller, more stable set of pages instead of several
   piecemeal ones.
6. **Basic SEO/social metadata** (meta description, OG tags) — after the UI
   pass, and after the methodology page exists to describe. Cheap, worth
   doing now that this is a real branded public site (OPSCI.ca) rather than
   a dev tool.
7. **Retirement-year comp-inflation investigation** — scoped research only
   (see below), no build commitment.
8. **Pre-2010 data (back to 1996)** — parked; explicitly undecided, and it's
   a `pssda_pipeline`-side data-sourcing question, not a portal task, so
   there's nothing to scope here yet.

### Detail on specific open items

- **Subsegment data exists but is almost entirely unexposed**: `SubSector`
  (Crown Agencies/Hospitals/Municipalities/Other Public Service/School
  Boards only, keyword-derived) sits in `employer_wide` unused beyond a
  single tag on the employer profile. `Segment` (Elementary/Secondary,
  School Boards only, ~62% coverage) is row-level and isn't in *any* cube
  yet — using it needs real pipeline work, not just a new query. `Rank_Norm`,
  `Segment_Norm`, and `French` exist as dictionary columns but are 0%
  populated — not usable yet, don't build around them.
- **"Similar employers" peer-grouping / recommendation**, per goal 3 above —
  the comparison *page* is built (any two employers, or the same position at
  two same-sector employers); what's still open is *suggesting* which
  employer to compare against. Needs a design conversation before building
  (same-size-tier? same-subsector? same-region? some combination?), the same
  open question the very first version of this brief raised and never
  resolved.
- **Monetization tier** — discussed early (API access, bulk export, custom
  benchmarking reports were the leading ideas), nothing built. Everything
  live today is free-tier. Not in the numbered plan above — revisit once
  the free-tier feature set feels more complete.
- **A known upstream data-quality bug, not ours to fix here**:
  `Title_Norm="ADMINISTRATION"` (at least at TDSB) conflates genuinely
  different roles spanning a $101K Finance Support Officer to a $236K CEO —
  a normalization-dictionary problem in `pssda_pipeline`, not something
  fixable from this repo. The composition breakdown (above) makes it
  visible rather than hidden where it's still shown, but doesn't correct it.

## Data gotchas — read `SUNSHINE.md` before writing a new aggregation

Every non-obvious field meaning, the three methodology rules
(new-entrant-≠-new-hire, matched-cohort raises, mid-year-move/leave
ambiguity), and the `Title_Norm` grouping rationale are documented there, not
repeated here. The short version: several `employment_history_enriched`
columns look self-explanatory and aren't (`TenureOnList`, `GapFlag`,
`YoYSalaryIncrease`'s `0.0` sentinel) — get this wrong and a chart looks fine
but asserts something false.
