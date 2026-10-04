from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RoleRaiseContext(BaseModel):
    # Placeholder for the role_trend cube's matched-cohort raise comparison (SUNSHINE.md #2).
    cohort_avg_yoy_increase: Optional[float] = None
    cohort_size: Optional[int] = None


class YearRecord(BaseModel):
    year: int
    employer_id: str
    employer_name: str
    sector_id: str
    sector_name: Optional[str] = None
    job_title: str
    title_norm: Optional[str] = None
    salary_paid: float
    taxable_benefits: float
    total_comp: float
    yoy_salary_increase: Optional[float] = None  # None, not the source's 0.0 sentinel, when not comparable
    yoy_total_comp_increase: Optional[float] = None
    comparable_to_prior_year: bool
    gap_flag: bool
    employer_switch_flag: bool
    promotion_flag: bool  # heuristic (title change + raise >=10%), not verified — label "possible promotion"
    role_raise_context: Optional[RoleRaiseContext] = None


class PaybandStanding(BaseModel):
    peer_group: Literal["employer", "employer_title", "sector_title"]  # no title-only tier — cross-domain titles aren't comparable
    peer_group_label: str
    year: int
    n_peers: int
    percentile: float
    rank: int


class CurrentRole(BaseModel):
    year: int
    employer_id: str
    employer_name: str
    sector_id: str
    sector_name: Optional[str] = None
    subsector: Optional[str] = None
    job_title: str
    title_norm: Optional[str] = None
    region: Optional[str] = None
    municipality: Optional[str] = None
    salary_paid: float
    taxable_benefits: float
    total_comp: float


class SectorOption(BaseModel):
    sector_id: str
    sector_name: str


class EmployeeSearchResult(BaseModel):
    # Lightweight — a search hit list, not a full profile.
    employee_id: str
    first_name: str
    last_name: str
    middle: Optional[str] = None
    current_employer_name: str
    current_job_title: str
    current_total_comp: float
    first_seen_year: int
    last_seen_year: int


class SearchOutcome(BaseModel):
    results: list[EmployeeSearchResult]
    too_many: bool  # True when the match count exceeded the cap — results is [] in that case
    # Set only for a search scoped to one employer (employer_id given) — an
    # entity with a known, bounded size, so instead of the "too many, narrow
    # your search" wall, it's paginated (or shown in full if small enough).
    # None for the general/fuzzy case, where too_many above is what applies.
    total_count: Optional[int] = None
    page: int = 1
    page_size: Optional[int] = None


class EmployeeProfile(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    middle: Optional[str] = None  # for disambiguation; not shown in the UI by default
    first_initial: Optional[str] = None

    first_seen_year: int
    first_seen_year_left_censored: bool  # True if first_seen_year == dataset floor (2010)
    last_seen_year: int
    years_disclosed: int  # count of years actually disclosed, not the span

    prob_female: Optional[float] = None  # name-based estimate; in the payload, not shown by default

    current: CurrentRole
    history: list[YearRecord] = Field(default_factory=list)
    paybands: list[PaybandStanding] = Field(default_factory=list)  # empty when Title_Norm unresolved
