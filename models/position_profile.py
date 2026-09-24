from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PositionYearRecord(BaseModel):
    year: int
    headcount: int
    avg_salary: float
    avg_total_comp: float
    # Count of PromotionFlag rows this year — a heuristic (title changed + raise
    # >=10%), not verified promotions.
    promotions: int
    # Matched-cohort average: only people who held this exact (sector, title) in
    # both this year and the prior year — not a same-role year-average diff.
    # See SUNSHINE.md #2. None when no matched cohort exists (e.g. the position's
    # first year in the data).
    avg_raise_matched: Optional[float] = None
    cohort_size_matched: int
    # Aggregate, name-based gender estimate — None below pipeline.gender.MIN_GROUP_SIZE.
    pct_female: Optional[float] = None


class PositionEmployerRank(BaseModel):
    rank: int
    employer_id: str
    employer_name: str
    headcount: int
    avg_total_comp: float
    max_salary: float
    # Headcount in their first disclosed year in this exact role at this
    # employer — not a hire count, see SUNSHINE.md #1.
    new_entrants: int
    # Matched-cohort average for this employer specifically; None when the
    # matched cohort here is too small (< MIN_EMPLOYER_GROUP_SIZE).
    avg_raise_matched: Optional[float] = None


class PositionSearchResult(BaseModel):
    sector_id: str
    title_norm: str
    sector_name: Optional[str] = None
    current_year: int
    current_headcount: int
    current_avg_total_comp: float


class PositionProfile(BaseModel):
    sector_id: str
    title_norm: str
    sector_name: Optional[str] = None

    first_year_present: int
    last_year_present: int
    years_present: int

    current: PositionYearRecord
    history: list[PositionYearRecord] = Field(default_factory=list)
    by_employer: list[PositionEmployerRank] = Field(default_factory=list)
