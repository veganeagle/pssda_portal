"""Runtime DuckDB connection over data/profiles/ cube tables. Never touches
data/processed (raw source) — a query that needs more than a cube provides is a
pipeline gap, not something to patch here with a live scan.
"""
import os

import duckdb

PROFILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "profiles"))

_PROFILE_TABLES = {
    "profile_wide": "profile_wide.parquet",
    "profile_history": "profile_history.parquet",
    "profile_payband_standing": "profile_payband_standing.parquet",
    "sectors": "sectors.parquet",
}

con = duckdb.connect(database=":memory:")
for view_name, filename in _PROFILE_TABLES.items():
    path = os.path.join(PROFILES_DIR, filename)
    if os.path.exists(path):
        con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM '{path}'")


def query(sql: str, params: list | None = None):
    return con.execute(sql, params or []).fetchdf()  # parameterized only — see README "Security pattern"
