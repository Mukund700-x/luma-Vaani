"""
Pagination utilities — consistent page/size/search contracts across all list endpoints.

Usage:
    @router.get("/", response_model=Page[HospitalSummary])
    async def list(params: Annotated[PageParams, Depends(pagination_dep)]) -> Page[HospitalSummary]:
        ...
"""

from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Validated pagination parameters extracted from query string."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    """Paginated response envelope used by all list endpoints."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def create(cls, items: list[T], total: int, params: PageParams) -> "Page[T]":
        pages = max(1, (total + params.size - 1) // params.size) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
            pages=pages,
        )


# ── FastAPI dependency ─────────────────────────────────────────────────────────

async def _pagination_dep(
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PageParams:
    return PageParams(page=page, size=size)


PaginationDep = Annotated[PageParams, Depends(_pagination_dep)]
