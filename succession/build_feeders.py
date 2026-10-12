"""Builds the feeders cube: for current-year incumbents of each position, the
position they held just before it (their previous run of a different
(SectorID, Title_Norm), ignoring years with no normalized title).

Province-wide (position_feeders) and per employer (employer_position_feeders,
keyed on the incumbent's current employer). Every role is built; the access
layer decides what's large enough to show.

Dev-time script: `python -m succession.build_feeders`.
"""
import os

import duckdb

from pipeline.manifest import update_manifest

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "profiles"))

MOVES_SQL = """
CREATE TABLE moves AS
WITH h AS (
    SELECT EmployeeID, Year, SectorID, EmployerID, Title_Norm, SalaryPaid
    FROM read_parquet($history) WHERE Title_Norm IS NOT NULL
),
cur AS (
    SELECT EmployeeID, SectorID, EmployerID, Title_Norm FROM h
    WHERE Year = (SELECT max(Year) FROM read_parquet($history))
),
runs AS (
    SELECT *, sum(chg) OVER (PARTITION BY EmployeeID ORDER BY Year) AS run
    FROM (
        SELECT *, CASE WHEN SectorID || '|' || Title_Norm
                       IS DISTINCT FROM lag(SectorID || '|' || Title_Norm) OVER (PARTITION BY EmployeeID ORDER BY Year)
                       THEN 1 ELSE 0 END AS chg
        FROM h WHERE EmployeeID IN (SELECT EmployeeID FROM cur)
    )
),
spans AS (
    SELECT EmployeeID, run,
           any_value(SectorID) AS sector_id, any_value(Title_Norm) AS title_norm, count(*) AS years,
           arg_min(SalaryPaid, Year) AS first_salary, arg_max(SalaryPaid, Year) AS last_salary,
           arg_min(EmployerID, Year) AS first_employer, arg_max(EmployerID, Year) AS last_employer,
           max(run) OVER (PARTITION BY EmployeeID) AS last_run
    FROM runs GROUP BY EmployeeID, run
)
SELECT c.EmployeeID, c.SectorID AS sector_id, c.Title_Norm AS title_norm, c.EmployerID AS employer_id,
       f.sector_id AS feeder_sector_id, f.title_norm AS feeder_title, f.years AS years_in_feeder,
       n.first_salary / f.last_salary - 1 AS pay_change,
       f.last_employer = n.first_employer AS same_employer
FROM cur c
JOIN spans n ON n.EmployeeID = c.EmployeeID AND n.run = n.last_run
LEFT JOIN spans f ON f.EmployeeID = c.EmployeeID AND f.run = n.last_run - 1
"""

# One row per (role, feeder); incumbents and with_feeder repeat on each row of a role.
AGG_SQL = """
WITH roles AS (
    SELECT {keys}, count(*) AS incumbents, count(feeder_title) AS with_feeder FROM moves GROUP BY ALL
)
SELECT {keys}, r.incumbents, r.with_feeder,
       m.feeder_sector_id, s.canonical AS feeder_sector_name, m.feeder_title,
       count(*) AS moved,
       count(*) / any_value(r.with_feeder) AS share,
       median(m.years_in_feeder) AS median_years_in_feeder,
       median(m.pay_change) AS median_pay_change,
       avg(m.same_employer::INTEGER) AS pct_same_employer
FROM moves m
JOIN roles r USING ({keys})
LEFT JOIN read_parquet($sectors) s ON s.sector_id::VARCHAR = m.feeder_sector_id
WHERE m.feeder_title IS NOT NULL
GROUP BY ALL
ORDER BY ALL
"""


def build():
    con = duckdb.connect()
    params = {
        "history": os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"),
        "sectors": os.path.join(SOURCE_DIR, "sectors_canonical.parquet"),
    }
    con.execute(MOVES_SQL, {"history": params["history"]})
    tables = {}
    for name, keys in (
        ("position_feeders", "sector_id, title_norm"),
        ("employer_position_feeders", "employer_id, sector_id, title_norm"),
    ):
        path = os.path.join(OUTPUT_DIR, f"{name}.parquet")
        con.execute(f"COPY ({AGG_SQL.format(keys=keys)}) TO '{path}' (FORMAT PARQUET)", {"sectors": params["sectors"]})
        tables[f"{name}.parquet"] = con.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]
    print(update_manifest("feeders", tables))


if __name__ == "__main__":
    build()
