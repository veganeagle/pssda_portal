"""Plain-language definitions of every measure the site shows. One list feeds
both the /data-dictionary page and the Dataset structured data
(variableMeasured) on that page and on /about-the-data.

Each definition was checked against the pipeline code that computes it
(pipeline/cubes/*, pipeline/rankings.py, pipeline/matched_cohort.py,
access/employee_search.py). Keep them in step if a calculation changes.
"""

SECTIONS = [
    ("Source fields", [
        ("Year", "The calendar year the pay was received, not the year the list was published."),
        ("Salary", "Salary paid in the year, as reported by the employer."),
        ("Taxable benefits", "Taxable benefits for the year, as reported by the employer. Reported separately from salary."),
        ("Total compensation", "Salary plus taxable benefits. It does not include pensions or non-taxable benefits."),
        ("Sector", "The disclosure category the employer reports under, e.g. School Boards or Hospitals and Boards of Public Health."),
        ("Employer", "An employer as reported on the list. Name variants of the same employer across years are combined into one."),
        ("Job title", "The title exactly as reported by the employer for that year."),
    ]),
    ("Groups and linking", [
        ("Employee (linked record)", "One person's disclosures linked across years by name, employer, title and other details. Linking is an estimate: records can occasionally be joined or split incorrectly."),
        ("Job group", "A normalized position that groups related job titles within a sector, so similar jobs can be compared across employers. Jobs in a group may still differ in duties or seniority."),
        ("Composition", "The original job titles that make up a job group at an employer, with how many people hold each."),
    ]),
    ("Counts and totals", [
        ("Disclosed employees", "The number of people on the list for a group in a year. Not the employer's full workforce: anyone paid under the threshold is not included."),
        ("Total disclosed salary", "The sum of salary paid to a group's disclosed employees in a year. Excludes taxable benefits, and covers only the disclosed part of an employer's pay."),
        ("Newly disclosed", "The share of a year's disclosed employees who appear on the list for the first time. Not a hiring rate: many had worked there for years and only crossed the threshold."),
        ("Attrition", "The share of people disclosed in a sector last year who are not on the list this year. Includes people who left and people whose pay fell below the threshold."),
    ]),
    ("Pay statistics", [
        ("Average salary", "The mean salary of a group's disclosed employees in a year."),
        ("Average total compensation", "The mean total compensation (salary plus taxable benefits) of a group's disclosed employees."),
        ("Median salary", "The middle salary of a group's disclosed employees in a year."),
        ("90th-percentile (P90) salary", "The salary that 90% of a group's disclosed employees are at or below."),
        ("Maximum salary", "The highest salary in a group in a year."),
    ]),
    ("Changes over time", [
        ("Same-person raise", "The average year-over-year change in salary for people who held the same job group in two consecutive years, with no gap. Employer-level figures also require the same employer. It compares the same people, not two group averages."),
        ("Change in average total compensation", "Shown on employer comparisons only: the change in a whole group's average total compensation from the prior year. It compares two different sets of people, so it is not a raise."),
        ("Promotion (estimated)", "Flagged when a person's job title changes and their salary rises by 10% or more in the same year. A heuristic, not a confirmed promotion."),
        ("Employer switch", "Flagged when a person appears under a different employer than the last time they were disclosed."),
        ("Gap", "Flagged when a person reappears after one or more years off the list. The reason (leave, reduced hours, pay below the threshold) is not known."),
    ]),
    ("Rankings and estimates", [
        ("Rank", "A person's position by total compensation among everyone disclosed in that year, within the province, a sector, an employer or a job group."),
        ("Peer standing", "A person's percentile by total compensation for the year within three groups: their employer, their job group at that employer, and their job group across the sector. Shown only for groups of three or more, and only when the job title maps to a job group."),
        ("Estimated % female", "An estimate from first names, shown only for groups of 20 or more people and never for individuals."),
    ]),
]

TERMS = [term for _, items in SECTIONS for term, _ in items]
