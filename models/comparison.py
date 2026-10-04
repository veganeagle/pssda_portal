from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ComparisonTrendYear(BaseModel):
    year: int
    headcount: int


class ComparisonSide(BaseModel):
    """One side (employer, or employer+position combo) of a comparison."""
    employer_id: str
    employer_name: str
    sector_id: str
    sector_name: Optional[str] = None
    current_year: int

    headcount: int
    prior_headcount: Optional[int] = None
    pct_headcount_growth: Optional[float] = None
    n_new: int
    n_attrition: int

    avg_salary: float
    avg_total_comp: float
    pct_benefits: Optional[float] = None
    disclosed_payroll: float
    # Employer mode: naive aggregate YoY change in avg_total_comp — NOT a
    # matched-cohort raise (no employer-wide matched-cohort figure exists).
    # Combo mode: the real matched-cohort raise, same as everywhere else.
    pct_comp_change: Optional[float] = None
    is_matched_raise: bool = False

    trend: list[ComparisonTrendYear] = Field(default_factory=list)


class RoleStats(BaseModel):
    headcount: int
    median_salary: float
    avg_raise_matched: Optional[float] = None


class RoleComparisonRow(BaseModel):
    title_norm: str
    a: Optional[RoleStats] = None
    b: Optional[RoleStats] = None


class EarnerStats(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    job_title: str
    title_norm: Optional[str] = None
    total_comp: float


class EarnerComparisonRow(BaseModel):
    a: Optional[EarnerStats] = None
    b: Optional[EarnerStats] = None


class EmployerComparison(BaseModel):
    a: ComparisonSide
    b: ComparisonSide
    roles: list[RoleComparisonRow] = Field(default_factory=list)
    earners: list[EarnerComparisonRow] = Field(default_factory=list)


class PositionComparison(BaseModel):
    title_norm: str
    a: ComparisonSide
    b: ComparisonSide
    earners: list[EarnerComparisonRow] = Field(default_factory=list)
