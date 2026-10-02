from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TrendYear(BaseModel):
    year: int
    headcount: int
    total_payroll: float


class SectorShare(BaseModel):
    sector_name: str
    headcount: int
    total_payroll: float


class FastMover(BaseModel):
    sector_id: str
    sector_name: str
    title_norm: str
    headcount: int
    avg_raise_matched: float


class TopEmployer(BaseModel):
    employer_id: str
    employer_name: str
    sector_name: Optional[str] = None
    headcount: int
    total_payroll: float


class TopPosition(BaseModel):
    sector_id: str
    sector_name: Optional[str] = None
    title_norm: str
    headcount: int
    median_salary: float
    avg_raise_matched: Optional[float] = None


class TopEarnerPreview(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    job_title: str
    employer_id: str
    employer_name: str
    total_comp: float


class NotableRoleLeader(BaseModel):
    role_label: str
    employee_id: str
    first_name: str
    last_name: str
    employer_id: str
    employer_name: str
    sector_name: Optional[str] = None
    job_title_raw: str
    salary_paid: float
    pool_size: int
    yoy_salary_increase: Optional[float] = None
    comparable_to_prior_year: bool = False


class HomeDashboard(BaseModel):
    current_year: int
    current_headcount: int
    current_payroll: float
    current_employers: int
    trend: list[TrendYear]
    sectors: list[SectorShare]
    fastest_movers: list[FastMover]
    top_employers: list[TopEmployer]
    top_positions: list[TopPosition]
    top_earners: list[TopEarnerPreview]
    notable_roles: list[NotableRoleLeader]
