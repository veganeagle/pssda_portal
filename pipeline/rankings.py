"""Shared current-year individual compensation rankings — one row per employee
disclosed in the dataset's latest year, with dense ranks against the whole
province, their sector, their employer, and their (sector, title_norm) position.
Used by pipeline/cubes/top_earners.py directly, and by employer_profile.py to
show "also ranks #N in sector" context on a top-10-at-this-employer list.
"""
import pandas as pd


def compute_current_year_rankings(history: pd.DataFrame) -> pd.DataFrame:
    max_year = int(history["Year"].max())
    cur = history[history["Year"] == max_year].copy()

    comparable = (cur["GapFlag"] == 0) & (cur["TenureOnList"] > 1)
    cur["YoYComparable"] = comparable
    cur["YoYSalaryIncreaseClean"] = cur["YoYSalaryIncrease"].where(comparable)

    cur["RankProvince"] = cur["TotalComp"].rank(method="dense", ascending=False).astype(int)
    cur["RankSector"] = cur.groupby("SectorID")["TotalComp"].rank(method="dense", ascending=False).astype(int)
    cur["RankEmployer"] = cur.groupby("EmployerID")["TotalComp"].rank(method="dense", ascending=False).astype(int)

    has_title = cur["Title_Norm"].notna()
    cur["RankPosition"] = float("nan")
    cur.loc[has_title, "RankPosition"] = (
        cur[has_title].groupby(["SectorID", "Title_Norm"])["TotalComp"].rank(method="dense", ascending=False)
    )

    return cur
