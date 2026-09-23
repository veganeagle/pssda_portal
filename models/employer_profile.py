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


class TopEarner(BaseModel):
    rank: int
    employee_id: str
    first_name: str
    last_name: str
    job_title: str
    total_comp: float


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
