from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from models.employer_profile import TitleVariant


class ComboYearRecord(BaseModel):
    year: int
    headcount: int
    avg_salary: float
    median_salary: float
    p90_salary: float
    max_salary: float
    avg_total_comp: float
    avg_raise_matched: Optional[float] = None
    pct_female: Optional[float] = None


class EmployerPositionProfile(BaseModel):
    employer_id: str
    employer_name: str
    sector_id: str
    sector_name: Optional[str] = None
    title_norm: str

    first_year_present: int
    last_year_present: int
    years_present: int

    current: ComboYearRecord
    history: list[ComboYearRecord] = Field(default_factory=list)
    # Real composition of this Title_Norm group at this employer — see
    # pipeline.title_breakdown.
    variants: list[TitleVariant] = Field(default_factory=list)
