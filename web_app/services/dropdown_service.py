import json
from pathlib import Path

DROPDOWN_DIR = Path("data/processed/dropdowns")

def load_cache():
    # Tolerate missing cache files: generate_dropdowns.py (which creates them)
    # itself imports the web_app package, which imports this module, so the
    # first-ever run needs this to succeed before the files exist.
    cache = {}
    for name in ["sectors", "employers", "titles", "regions"]:
        file = DROPDOWN_DIR / f"{name}.json"
        if file.exists():
            with open(file) as f:
                cache[name] = json.load(f)
        else:
            cache[name] = []
    return cache

dropdown_cache = load_cache()

# ---------------------------------------------------------------------
# EMPLOYERS
# ---------------------------------------------------------------------
def filter_employers(sector_id=None):
    employers = dropdown_cache["employers"]
    if sector_id:
        return [
            {"EmployerID": e["EmployerID"], "EmployerName": e["EmployerName"]}
            for e in employers if str(e["SectorID"]) == str(sector_id)
        ]
    return [
        {"EmployerID": e["EmployerID"], "EmployerName": e["EmployerName"]}
        for e in employers
    ]

# ---------------------------------------------------------------------
# TITLES
# ---------------------------------------------------------------------
def filter_titles(sector_id=None, employer_id=None, region=None):
    titles = dropdown_cache["titles"]
    filtered = titles
    if sector_id:
        filtered = [t for t in filtered if str(t["SectorID"]) == str(sector_id)]
    if employer_id:
        filtered = [t for t in filtered if t["EmployerID"] == employer_id]
    if region and region not in ("All", ""):
        filtered = [t for t in filtered if t.get("Region") == region]
    return sorted({t["Title"] for t in filtered})

# ---------------------------------------------------------------------
# REGIONS
# ---------------------------------------------------------------------
def filter_geography(region=None, geo=None):
    # Regions is a small static deduplicated list (see generate_dropdowns.py) — not
    # currently filtered by sector/employer, but the params are accepted (and
    # ignored) since views/api.py's /api/regions route passes them through.
    return dropdown_cache["regions"]
