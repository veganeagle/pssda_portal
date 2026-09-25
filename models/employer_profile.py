from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EmployerYearRecord(BaseModel):
    year: int
    headcount: int
    avg_salary: float
    avg_total_comp: float
    total_payroll: float
    # Share of headcount in their first disclosed year at this employer — NOT a
    # hiring/turnover rate. See SUNSHINE.md #1: many of these already worked here
    # and simply crossed $100K this year.
    pct_newly_disclosed: float
    # Aggregate, name-based gender estimate — None below pipeline.gender.MIN_GROUP_SIZE.
    pct_female: Optional[float] = None


class TopEarner(BaseModel):
    rank: int
    employee_id: str
    first_name: str
    last_name: str
    job_title: str
    total_comp: float
    yoy_salary_increase: Optional[float] = None
    comparable_to_prior_year: bool
    # Rank against the whole sector / this exact (sector, title) position,
    # province-wide — only available when this employer's "current" year is the
    # dataset's actual latest year (see pipeline docstring).
    rank_sector: Optional[int] = None
    sector_pool: Optional[int] = None
    rank_position: Optional[int] = None
    position_pool: Optional[int] = None


class TitleVariant(BaseModel):
    # A raw JobTitleNorm variant large enough (see pipeline.title_breakdown) to
    # name individually within a Title_Norm group, or "Other" for the residual.
    variant: str
    headcount: int
    avg_salary: float
    median_salary: float


class TopPosition(BaseModel):
    rank: int
    sector_id: str
    title_norm: str
    headcount: int
    avg_salary: float
    median_salary: float
    p90_salary: float
    avg_total_comp: float
    # Matched-cohort average for this position at this employer; None when the
    # matched cohort here is too small (< MIN_MATCHED_COHORT).
    avg_raise_matched: Optional[float] = None
    # Real composition of this Title_Norm group at this employer — e.g. Teacher
    # here is Elementary + Secondary + a few others, never just one of them.
    variants: list[TitleVariant] = Field(default_factory=list)


class EmployerSearchResult(BaseModel):
    employer_id: str
    employer_name: str
    sector_id: str
    sector_name: Optional[str] = None
    current_year: int
    current_headcount: int
    current_avg_total_comp: float


class EmployerProfile(BaseModel):
    employer_id: str
    employer_name: str
    sector_id: str
    sector_name: Optional[str] = None
    subsector: Optional[str] = None
    region: Optional[str] = None
    municipality: Optional[str] = None
    population: Optional[float] = None  # municipal employers only

    first_year_present: int
    last_year_present: int
    years_present: int

    current: EmployerYearRecord
    history: list[EmployerYearRecord] = Field(default_factory=list)
    top_earners: list[TopEarner] = Field(default_factory=list)
    top_positions: list[TopPosition] = Field(default_factory=list)
