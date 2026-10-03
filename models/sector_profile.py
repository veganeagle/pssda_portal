from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from models.home_dashboard import FastMover, TopEmployer, TopPosition, TrendYear


class PositionShare(BaseModel):
    title_norm: str
    headcount: int


class SectorTopPosition(BaseModel):
    title_norm: str
    headcount: int
    median_salary: float
    employee_id: str
    first_name: str
    last_name: str
    employer_id: str
    employer_name: str
    salary_paid: float
    yoy_salary_increase: Optional[float] = None
    comparable_to_prior_year: bool = False


class SectorProfile(BaseModel):
    sector_id: str
    sector_name: str
    current_year: int
    current_headcount: int
    current_employers: int
    current_payroll: float
    yoy_payroll_change: Optional[float] = None
    common_positions: list[str]
    trend: list[TrendYear]
    fastest_movers: list[FastMover]
    position_mix: list[PositionShare]
    top_employers: list[TopEmployer]
    top_positions: list[SectorTopPosition]
    top_roles: list[TopPosition]
