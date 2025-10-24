"""Pydantic schemas for quote API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MemberRef(BaseModel):
    """Reference to a Member."""

    id: str
    display_name: str
    username: str | None


class QuoteResponse(BaseModel):
    """Response schema for a quote."""

    id: str
    number: int
    text: str
    quotee: MemberRef
    quoter: MemberRef
    year: int
    created_at: datetime


class QuoteCreateRequest(BaseModel):
    """Request schema for creating a quote."""

    text: str
    quotee_username: str
    quoter_username: str


class QuoteUpdateRequest(BaseModel):
    """Request schema for updating a quote."""

    text: str | None = None
    quotee_username: str | None = None
    quoter_username: str | None = None
    year: int | None = None


class QuoteSearchResponse(BaseModel):
    """Response schema for quote search results."""

    quotes: list[QuoteResponse]
    total_matches: int


class QuoteStatsResponse(BaseModel):
    """Response schema for user quote statistics."""

    total_quotes: int
    first_quote_year: int | None
    last_quote_year: int | None
    average_length: float
