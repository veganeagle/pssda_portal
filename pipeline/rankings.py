"""Shared per-year individual compensation rankings — one row per employee
disclosed in a given year, with dense ranks against the whole province,
their sector, their employer, and their (sector, title_norm) position.
Used by pipeline/cubes/top_earners.py (every year, for the year-by-year
leaderboard) and by employer_profile.py to show "also ranks #N in sector"
context on a top-10-at-this-employer list (current year only).
"""
import pandas as pd


def compute_rankings_for_year(history: pd.DataFrame, year: int) -> pd.DataFrame:
    cur = history[history["Year"] == year].copy()

    comparable = (cur["GapFlag"] == 0) & (cur["TenureOnList"] > 1)
    cur["YoYComparable"] = comparable
    cur["YoYSalaryIncreaseClean"] = cur["YoYSalaryIncrease"].where(comparable)

    cur["RankProvince"] = cur["TotalComp"].rank(method="dense", ascending=False).astype(int)
    cur["ProvincePool"] = len(cur)

    cur["RankSector"] = cur.groupby("SectorID")["TotalComp"].rank(method="dense", ascending=False).astype(int)
    cur["SectorPool"] = cur.groupby("SectorID")["TotalComp"].transform("size")

    cur["RankEmployer"] = cur.groupby("EmployerID")["TotalComp"].rank(method="dense", ascending=False).astype(int)
    cur["EmployerPool"] = cur.groupby("EmployerID")["TotalComp"].transform("size")

    has_title = cur["Title_Norm"].notna()
    cur["RankPosition"] = float("nan")
    cur["PositionPool"] = float("nan")
    cur.loc[has_title, "RankPosition"] = (
        cur[has_title].groupby(["SectorID", "Title_Norm"])["TotalComp"].rank(method="dense", ascending=False)
    )
    cur.loc[has_title, "PositionPool"] = (
        cur[has_title].groupby(["SectorID", "Title_Norm"])["TotalComp"].transform("size")
    )

    return cur


def compute_current_year_rankings(history: pd.DataFrame) -> pd.DataFrame:
    return compute_rankings_for_year(history, int(history["Year"].max()))
