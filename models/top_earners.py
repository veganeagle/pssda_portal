from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TopEarnerRow(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    year: int
    employer_id: str
    employer_name: str
    sector_id: str
    sector_name: Optional[str] = None
    title_norm: Optional[str] = None
    job_title: str
    salary_paid: float
    taxable_benefits: float
    total_comp: float
    yoy_salary_increase: Optional[float] = None
    comparable_to_prior_year: bool
    rank_province: int
    province_pool: int
    rank_sector: int
    sector_pool: int
    rank_employer: int
    employer_pool: int
    rank_position: Optional[int] = None
    position_pool: Optional[int] = None
