
BASELINE_YEAR = 2025          # latest year in this dataset
YEARS_WINDOW = 3              # number of years to include in panel
CONTINUOUS_DEFAULT = True     # require same employees across all years
EXPORT_NAMES_DEFAULT = False  # default privacy setting
YEARS_RANGE = list(range(BASELINE_YEAR - (YEARS_WINDOW - 1), BASELINE_YEAR + 1))

# Whitelist of user-facing filter keys -> SQL column reference. build_panel_query()
# only accepts keys present here — anything else is dropped, not interpolated, to
# keep filter keys (not just values) out of the SQL string.
COLUMN_MAP = {
    "Year": "h.Year",
    "Sector": "h.SectorID",
    "Employer": "h.EmployerName",
    "EmployerID": "h.EmployerID",
    "Municipality": "h.Municipality",
    "Region": "h.Region",
    "GeographicArea": "h.GeographicArea",
    "JobTitle": "h.JobTitleNorm",
    "TitleNorm": "h.Title_Norm",
    "Salary": "h.SalaryPaid",
    "Benefits": "h.TaxableBenefits",
    "Raise": "h.YoYSalaryIncrease",
    "Tenure": "h.TenureOnList",
    "Gender": "e.Prob_Female",
}
