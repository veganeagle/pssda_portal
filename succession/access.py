"""Feeder positions for one position, province-wide or at one employer: where
its current-year incumbents came from. Reads only the feeders cube in
data/profiles (succession/build_feeders.py)."""
from __future__ import annotations

import os
from functools import lru_cache

from access._rows import records
from access.db import PROFILES_DIR, con, query

for _view in ("position_feeders", "employer_position_feeders"):
    _path = os.path.join(PROFILES_DIR, f"{_view}.parquet")
    if os.path.exists(_path):
        con.execute(f"CREATE OR REPLACE VIEW {_view} AS SELECT * FROM '{_path}'")

MIN_SHARE = 0.05      # a previous position must be at least this share of the moves in
MIN_MOVED = 3         # and at least this many people: fewer is one or two careers, often a matching error
MIN_EXPLAINED = 0.20  # shown positions must account for this share of incumbents, else the
# role is mostly people who grew into it below the $100K line and the table explains nothing


@lru_cache(maxsize=256)
def feeders(sector_id: str, title_norm: str, employer_id: str | None = None) -> dict | None:
    if employer_id is None:
        df = query("SELECT * FROM position_feeders WHERE sector_id = ? AND title_norm = ? AND share >= ? AND moved >= ? "
                   "ORDER BY moved DESC, feeder_title", [sector_id, title_norm, MIN_SHARE, MIN_MOVED])
    else:
        df = query("SELECT * FROM employer_position_feeders WHERE employer_id = ? AND sector_id = ? AND title_norm = ? "
                   "AND share >= ? AND moved >= ? ORDER BY moved DESC, feeder_title",
                   [employer_id, sector_id, title_norm, MIN_SHARE, MIN_MOVED])
    rows = records(df)
    if not rows:
        return None
    explained = sum(r["moved"] for r in rows)
    if explained / rows[0]["incumbents"] < MIN_EXPLAINED:
        return None
    return {"incumbents": rows[0]["incumbents"], "explained": explained, "rows": rows}


if __name__ == "__main__":
    for args in (("10", "PRINCIPAL"), ("8", "SERGEANT"), ("10", "TEACHER")):
        f = feeders(*args)
        print(args, f and (f["incumbents"], f["explained"], [(r["feeder_title"], r["moved"]) for r in f["rows"]]))
    emp = query("SELECT employer_id FROM employer_position_feeders WHERE sector_id='10' AND title_norm='PRINCIPAL' "
                "ORDER BY incumbents DESC LIMIT 1").iloc[0, 0]
    f = feeders("10", "PRINCIPAL", emp)
    print(emp, f["incumbents"], [(r["feeder_title"], r["moved"], r["pct_same_employer"]) for r in f["rows"][:3]])
