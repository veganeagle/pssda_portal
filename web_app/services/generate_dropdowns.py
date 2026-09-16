import duckdb, json
from pathlib import Path
from web_app.config import BASELINE_YEAR

OUTPUT = Path("data/processed/dropdowns")
OUTPUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(database=":memory:")

# --- SECTORS ----------------------------------------------------------
sectors = con.execute("""
    SELECT DISTINCT 
        sector_id AS SectorID,
        canonical AS SectorName
    FROM read_parquet('data/processed/sectors_canonical.parquet')
    WHERE sector_id IS NOT NULL
    ORDER BY SectorName;
""").fetchdf().to_dict(orient="records")

# --- EMPLOYERS --------------------------------------------------------
employers = con.execute(f"""
    WITH active AS (
        SELECT DISTINCT EmployerID 
        FROM read_parquet('data/processed/employment_history_enriched.parquet')
        WHERE Year = {BASELINE_YEAR}
    )
    SELECT DISTINCT 
        e.CanonicalEmployerID AS EmployerID,
        e.CanonicalEmployer   AS EmployerName,
        e.CanonicalSectorID   AS SectorID
    FROM read_parquet('data/processed/employer/employers_canonical.parquet') e
    JOIN active a ON a.EmployerID = e.CanonicalEmployerID
    WHERE e.CanonicalEmployerID IS NOT NULL 
      AND e.CanonicalSectorID IS NOT NULL
      AND e.CanonicalSectorID != -1
    ORDER BY EmployerName;
""").fetchdf().to_dict(orient="records")

# --- TITLES -----------------------------------------------------------
# Defensive check: handle Title_Norm vs JobTitleNorm
cols = [c[0] for c in con.execute(
    "DESCRIBE SELECT * FROM read_parquet('data/processed/employment_history_enriched.parquet')"
).fetchall()]
title_col = "Title_Norm" if "Title_Norm" in cols else "JobTitleNorm"

titles = con.execute(f"""
    SELECT DISTINCT 
        "{title_col}" AS Title,
        EmployerID,
        SectorID,
        Region
    FROM read_parquet('data/processed/employment_history_enriched.parquet')
    WHERE Year = {BASELINE_YEAR} AND "{title_col}" IS NOT NULL
    ORDER BY SectorID, EmployerID, Title;
""").fetchdf().to_dict(orient="records")

# --- REGIONS ----------------------------------------------------------
regions = con.execute("""
    SELECT DISTINCT 
        CASE
            WHEN Region IS NULL OR Region ILIKE 'NA' OR Region ILIKE 'UNKNOWN' THEN 'Unknown'
            ELSE Region 
        END AS Region
    FROM read_parquet('data/processed/employer/employers_canonical.parquet')
""").fetchdf()["Region"].dropna().unique().tolist()

if "All" not in regions:
    regions.insert(0, "All")

# --- SAVE -------------------------------------------------------------
with open(OUTPUT / "sectors.json", "w") as f: json.dump(sectors, f, indent=2)
with open(OUTPUT / "employers.json", "w") as f: json.dump(employers, f, indent=2)
with open(OUTPUT / "titles.json", "w") as f: json.dump(titles, f, indent=2)
with open(OUTPUT / "regions.json", "w") as f: json.dump(regions, f, indent=2)

print(f"Dropdown data generated in {OUTPUT}")
