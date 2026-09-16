from web_app.db import query
from web_app.config import COLUMN_MAP

def build_panel_query(filters, years, names=False):
    start_year, end_year = min(years), max(years)
    conditions = ["h.Year BETWEEN ? AND ?"]
    params = [start_year, end_year]

    for key, val in filters.items():
        # Whitelist-only: keys not in COLUMN_MAP are dropped rather than
        # interpolated as a raw column reference (column/identifier names
        # can't be parameterized in SQL, so this has to be an allowlist).
        col = COLUMN_MAP.get(key)
        if col is None or val in (None, "", "All"):
            continue

        # Handle lists (e.g., multiple employers or regions)
        if isinstance(val, list):
            if not val:
                continue
            placeholders = ",".join(["?"] * len(val))
            conditions.append(f"{col} IN ({placeholders})")
            params.extend(val)

        # Handle user-typed job title search
        elif key == "JobTitle":
            conditions.append(f"LOWER({col}) LIKE LOWER(?)")
            params.append(f"%{val}%")

        # Handle canonical title equality
        elif key == "TitleNorm":
            conditions.append(f"{col} = ?")
            params.append(val)

        # Handle fuzzy text matches (EmployerName, Rank, Segment)
        elif any(tok in col.lower() for tok in ["employer", "rank", "segment"]):
            conditions.append(f"LOWER({col}) LIKE LOWER(?)")
            params.append(f"%{val}%")

        # Default equality
        else:
            conditions.append(f"{col} = ?")
            params.append(val)

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT
            h.Year,
            COUNT(*) AS CountEmployees,
            COUNT(CASE WHEN h.TenureOnList > 1 THEN 1 END) AS ReturningEmployees,
            ROUND(AVG(h.SalaryPaid), 0) AS AvgSalary,
            ROUND(AVG(CASE WHEN h.TenureOnList = 1 THEN h.SalaryPaid END), 0) AS AvgNewSalary,
            ROUND(AVG(CASE WHEN h.TenureOnList > 1 THEN h.SalaryPaid END), 0) AS AvgReturningSalary,
            ROUND(AVG(CASE WHEN h.TenureOnList > 1 THEN h.YoYSalaryIncrease END), 2) AS AvgRaiseReturning,
            ROUND(AVG(CASE WHEN e.Prob_Female >= 0.5 THEN 1 ELSE 0 END) * 100, 1) AS PercentFemale,
            COUNT(DISTINCT h.EmployerID) AS NumEmployers,
            ROUND(AVG(h.TaxableBenefits), 0) AS AvgTaxableBenefits
            {", STRING_AGG(e.FirstName || ' ' || e.LastName, ', ') AS Names" if names else ""}
        FROM employment_history_enriched h
        LEFT JOIN employees_enriched e ON h.EmployeeID = e.EmployeeID
        WHERE {where_clause}
        GROUP BY h.Year
        ORDER BY h.Year;
    """

    return query(sql, params)
