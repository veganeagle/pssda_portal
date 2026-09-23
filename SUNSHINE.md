# Background: The Ontario Sunshine List

This document is context for anyone (human or AI) working on this project —
what the underlying disclosure actually is, why it exists, and — most
importantly — how its mechanics constrain what our analytics are allowed to
claim. Read the last section before writing any aggregation logic.

## What it is

The **Public Sector Salary Disclosure Act, 1996** requires every
organization that receives significant provincial funding — provincial
ministries, municipalities, hospitals, school boards, universities and
colleges, Crown agencies, and similar public bodies — to publish the name,
position/title, salary, and taxable benefits of every employee paid
**$100,000 or more** in a calendar year. It's published annually, typically
in late March, for the prior calendar year (the 2025 disclosure was released
in March 2026). "Sunshine list" is the informal name; the province's own
name for it is the disclosure this Act requires.

## Where the idea came from

The "sunshine law" concept originates in American open-government
legislation — Florida's Government in the Sunshine Law (1967) and the
federal Government in the Sunshine Act (1976), both aimed at open public
meetings rather than salaries specifically. In Ontario, then-provincial
treasurer Frank Miller floated a salary-disclosure "sunshine law" in 1982
(at a $30,000 threshold), but it stalled under union opposition. The Harris
government revived and passed the idea in 1996 under Finance Minister Ernie
Eves, reportedly publishing the first list just 90 days after the enabling
legislation received assent.

## Purpose

The stated rationale is straightforward public-accountability transparency:
taxpayers fund these salaries, so taxpayers (and the press) should be able
to see how much public money goes to compensation, at the individual level,
for anyone earning above a threshold considered clearly "public interest."

## The threshold has never moved

This is the single most consequential fact about the dataset for anyone
building analytics on it: **the $100,000 threshold has never been adjusted
for inflation since 1996.** $100,000 in 1996 is roughly $175,000–$185,000 in
today's dollars. As a direct result, the list has grown enormously — from
about 4,500 people in 1996 to roughly 405,000 in 2025, a ~90x increase —
almost entirely because ordinary wage growth has pulled more and more
non-executive roles over a fixed line, not because the public sector
workforce grew 90x. Our dataset's 2010–2025 window sits inside this same
unindexed regime throughout.

## Known criticisms (useful context, not our problem to fix)

- **List bloat / loss of meaning**: by the late 2010s, commentators
  described the list as a "data dump" — too large and too heterogeneous
  (wildly different seniority levels, no standardized job titles across
  thousands of independent employers) to support easy comparison. This is
  precisely the gap `pssda_pipeline`'s entity resolution and title
  normalization (`Title_Norm`, `EmployerID`, `SubSector`) exists to close —
  our project's value proposition is largely "do the normalization work the
  raw list never did."
- **Possible wage-leverage effect**: some critics argue publishing salaries
  gives employees negotiating information they wouldn't otherwise have.
- **Enforcement gaps**: compliance is uneven; there are documented cases of
  entities/individuals evading disclosure (e.g., Ornge's CEO in 2011).

## An unintended research asset

The unindexed threshold is usually framed only as a flaw (see "Known
criticisms" above) — it was meant to flag genuinely high earners, and
instead now catches a large and growing share of ordinary public-sector
roles that simply drifted past a fixed nominal line. But that same drift is
what makes this dataset valuable to us: a threshold that hasn't moved in 30
years, applied every year to the same class of employers, has produced a
large, consistent, longitudinal, publicly available near-census of Ontario
public-sector compensation — something that essentially doesn't exist for
any other jurisdiction or workforce at this scale outside of proprietary
compensation-survey data. The 2025 disclosure alone covers roughly 405,000
people; ours spans 16 years and 2.94M employee-year records.

That scale and continuity is what makes several genuinely hard questions
answerable that a smaller or shorter-run dataset couldn't support: union
compensation benchmarking against real peer employers rather than a small
survey sample, statistical outlier detection (pay that's anomalous for a
role/employer/region — a legitimate first-pass signal for further scrutiny,
fraud or otherwise), regional pay disparity analysis at a granularity most
provinces don't publish, and — because we have enough rows to isolate
variables — actually modeling *what drives compensation* for a given role
(tenure vs. employer size vs. region vs. sector) rather than just reporting
averages. This is an underused asset largely because the raw list itself
has never been normalized or linked across years; that normalization is
this project's core value-add on top of the disclosure.

## Implications for this project — read before writing any aggregation

Three mechanics of *how* the list works directly break naive year-over-year
analysis. All three came up in scoping this project and need to be design
rules, not afterthoughts.

### 1. "New entrant" means newly crossed $100K, not newly hired

`TenureOnList = 1` (confirmed against `employees_enriched.FirstSeenYear` —
they always agree) means **this is the first year this person appears on
the disclosure**, full stop. That happens for several very different real
reasons that our data cannot distinguish from each other:

- an actual new hire whose starting salary is already >$100K,
- an existing long-tenured employee who crossed the threshold this year via
  a raise or promotion,
- someone returning to the list after a dip below $100K (part-time,
  reduced hours, secondment) that isn't itself flagged anywhere,
- someone returning after an unpaid leave (see #3).

**Rule:** never label this metric "new hires" or "turnover" in any UI copy
or export. Call it what it is — "newly disclosed" / "newly over threshold."
If we ever want a true new-hire signal, it would need to come from salary
level + role context (e.g., an entry-level title newly appearing), not from
`TenureOnList` alone, and should be presented as an estimate.

### 2. Role-level "raise" must be same-incumbent, not same-role-average

Comparing the average salary of "Police Sergeant" in 2025 against 2024 is
**not** a raise number — it's contaminated by mix-shift: sergeants who
newly crossed threshold this year, sergeants who retired/left/dropped off
last year, and only partially the sergeants present in both years actually
getting a raise. A naive `AVG(SalaryPaid) WHERE Title_Norm='Police Sergeant'
GROUP BY Year` and diffing the two years answers a different question
("how did average sergeant pay differ between two different sets of
people") than "did sergeants get a raise" (how did the *same* people's pay
change).

The pipeline already computes the right thing at the row level:
`YoYSalaryIncrease`, which is only meaningful where `TenureOnList > 1` (a
same-employee prior-year comparison exists) — per the existing brief's
gotcha, `YoYSalaryIncrease = 0.0` can mean "no prior year to compare," not
"flat pay," so that gating has to be applied everywhere, not just where it
happens to matter.

**Rule for the cube pipeline:** any role/employer "raise %" cube must be
built as a **matched-cohort aggregate** — average `YoYSalaryIncrease` over
the subset of people present in the role in both the current and prior
year — kept as a *separate* cube/metric from a "headcount and average pay
of everyone disclosed this year" cube. The two answer different questions
and must never be blended into one number or shown without labeling which
one a chart is displaying.

### 3. Mid-year employer moves and leaves complicate a single "Year" row

The disclosure is one row per employee **per calendar year**, and our
processed data confirms there are zero cases of one `EmployeeID` having two
rows in the same `Year` — mid-year moves get collapsed into a single annual
figure by the upstream pipeline. Two things fall out of that:

- **Mid-year employer switch**: `EmployerSwitchFlag` marks a change of
  employer *between* consecutive disclosed years, but for the switch year
  itself we can't see the split between old and new employer — the
  `SalaryPaid`/`EmployerID` for that year is whatever the pipeline resolved
  it to (not independently verified here; worth confirming against
  `pssda_pipeline`'s dedup logic before trusting employer attribution or
  full-year salary comparability in switch years specifically).
- **Leave (maternity/parental/other unpaid leave)**: not flagged anywhere
  in the source data. A leave year can show as a large apparent pay cut
  (partial year worked) with a rebound the next year that would misread as
  a large raise, or can push someone below $100K entirely for a year —
  indistinguishable in our data from an actual departure, and
  indistinguishable on return from a genuine new entrant. `GapFlag` catches
  "reappeared after an absence," but not *why*.

**Rule:** never render user-facing copy that asserts someone "left" or is
"new" based on a single year's presence/absence — use neutral phrasing
("not disclosed in `<year>`"), and treat `EmployerSwitchFlag = 1` years and
single-year absences as lower-confidence data points, not as clean signal,
anywhere we compute raise/tenure/new-entrant metrics.

## Sources

- [Sunshine list — Wikipedia](https://en.wikipedia.org/wiki/Sunshine_list)
- [What Is the Ontario Sunshine List? Rules, Threshold & History](https://sunshinelister.ca/ontario/about)
- [The Ontario Sunshine List History — PublicPayPulse](https://publicpaypulse.com/public-sector-insights/2025/10/15/the-ontario-sunshine-list-history/)
- [Province Should Adjust $100,000 Threshold For Sunshine List, or Abandon it — The Meaford Independent](https://themeafordindependent.ca/province-should-adjust-100000-threshold-for-sunshine-list-or-abandon-it/)
