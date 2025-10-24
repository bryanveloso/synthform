"""Quote API endpoints."""

from __future__ import annotations

import logging
from datetime import datetime

from asgiref.sync import sync_to_async
from django.db.models import Avg
from django.db.models import Count
from django.db.models import Max
from django.db.models import Min
from django.db.models import Q
from django.db.models.functions import Length
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Query
from ninja import Router

from events.models import Member

from .models import Quote
from .schemas import MemberRef
from .schemas import QuoteCreateRequest
from .schemas import QuoteResponse
from .schemas import QuoteSearchResponse
from .schemas import QuoteStatsResponse
from .schemas import QuoteUpdateRequest

logger = logging.getLogger(__name__)
router = Router(tags=["quotes"])


def _quote_to_response(quote: Quote) -> QuoteResponse:
    """Convert Quote model to response schema."""
    return QuoteResponse(
        id=str(quote.id),
        number=quote.number,
        text=quote.text,
        quotee=MemberRef(
            id=str(quote.quotee.id),
            display_name=quote.quotee.display_name,
            username=quote.quotee.username,
        ),
        quoter=MemberRef(
            id=str(quote.quoter.id),
            display_name=quote.quoter.display_name,
            username=quote.quoter.username,
        ),
        year=quote.year,
        created_at=quote.created_at,
    )


@router.get("/", response=dict)
async def list_quotes(
    request,
    page: int = Query(1, gt=0),
    per_page: int = Query(100, gt=0, le=100),
) -> dict:
    """List all quotes with pagination.

    Args:
        page: Page number (starts at 1)
        per_page: Number of quotes per page (1-100, default 100)
    """
    queryset = Quote.objects.select_related("quotee", "quoter").order_by("-number")

    total = await queryset.acount()
    total_pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page

    quotes = []
    async for quote in queryset[offset : offset + per_page]:
        quotes.append(_quote_to_response(quote))

    return {
        "quotes": quotes,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }


@router.get("/users", response=list[dict])
async def list_all_users(request) -> list[dict]:
    """Get all users who have been quoted with statistics."""
    from django.db.models.functions import Min, Max

    queryset = (
        Quote.objects.values(
            "quotee__username",
            "quotee__display_name",
        )
        .annotate(
            quote_count=Count("id"),
            first_quote_date=Min("created_at"),
            last_quote_date=Max("created_at"),
        )
        .order_by("-quote_count")
    )

    users = []
    async for user_data in queryset:
        users.append({
            "quotee": user_data["quotee__display_name"] or user_data["quotee__username"],
            "quote_count": user_data["quote_count"],
            "first_quote_date": user_data["first_quote_date"].isoformat() if user_data["first_quote_date"] else None,
            "last_quote_date": user_data["last_quote_date"].isoformat() if user_data["last_quote_date"] else None,
        })

    return users


@router.get("/random", response=list[QuoteResponse])
async def get_random_quotes(
    request, limit: int = Query(1, gt=0, le=100)
) -> list[QuoteResponse]:
    """Get random quote(s).

    Args:
        limit: Number of quotes to return (1-100, default 1)
    """
    quotes = []
    async for quote in Quote.objects.select_related("quotee", "quoter").order_by("?")[
        :limit
    ]:
        quotes.append(_quote_to_response(quote))
    return quotes


@router.get("/latest", response=list[QuoteResponse])
async def get_latest_quotes(
    request, limit: int = Query(1, gt=0, le=100)
) -> list[QuoteResponse]:
    """Get latest quote(s) by creation date.

    Args:
        limit: Number of quotes to return (1-100, default 1)
    """
    quotes = []
    async for quote in Quote.objects.select_related("quotee", "quoter").order_by(
        "-created_at"
    )[:limit]:
        quotes.append(_quote_to_response(quote))
    return quotes


@router.get("/search", response=QuoteSearchResponse)
async def search_quotes(
    request,
    q: str = Query(..., min_length=1),
    limit: int = Query(25, gt=0, le=100),
    random: bool = Query(False),
) -> QuoteSearchResponse:
    """Search quotes by text.

    Args:
        q: Search query
        limit: Number of results to return (1-100, default 25)
        random: Return results in random order
    """
    queryset = Quote.objects.select_related("quotee", "quoter").filter(
        text__icontains=q
    )

    total = await queryset.acount()

    if random:
        queryset = queryset.order_by("?")
    else:
        queryset = queryset.order_by("-created_at")

    quotes = []
    async for quote in queryset[:limit]:
        quotes.append(_quote_to_response(quote))

    return QuoteSearchResponse(quotes=quotes, total_matches=total)


@router.get("/by-user/{username}", response=QuoteSearchResponse)
async def get_quotes_by_user(
    request,
    username: str,
    limit: int = Query(25, gt=0, le=100),
    random: bool = Query(False),
) -> QuoteSearchResponse:
    """Get quotes by user (quotee).

    Args:
        username: Username to search for
        limit: Number of results to return (1-100, default 25)
        random: Return results in random order
    """
    queryset = Quote.objects.select_related("quotee", "quoter").filter(
        Q(quotee__username__iexact=username)
        | Q(quotee__display_name__icontains=username)
    )

    total = await queryset.acount()

    if random:
        queryset = queryset.order_by("?")
    else:
        queryset = queryset.order_by("-created_at")

    quotes = []
    async for quote in queryset[:limit]:
        quotes.append(_quote_to_response(quote))

    return QuoteSearchResponse(quotes=quotes, total_matches=total)


@router.get("/stats/{username}", response=QuoteStatsResponse)
async def get_user_stats(request, username: str) -> QuoteStatsResponse:
    """Get statistics for a user's quotes.

    Args:
        username: Username to get stats for
    """
    queryset = Quote.objects.filter(
        Q(quotee__username__iexact=username)
        | Q(quotee__display_name__icontains=username)
    )

    stats = await queryset.aaggregate(
        total=Count("id"),
        first_year=Min("year"),
        last_year=Max("year"),
        avg_length=Avg(Length("text")),
    )

    return QuoteStatsResponse(
        total_quotes=stats["total"] or 0,
        first_quote_year=stats["first_year"],
        last_quote_year=stats["last_year"],
        average_length=stats["avg_length"] or 0.0,
    )


@router.get("/{number}", response=QuoteResponse)
async def get_quote_by_number(request, number: int) -> QuoteResponse:
    """Get a specific quote by its number.

    Args:
        number: The quote number
    """
    quote = await sync_to_async(get_object_or_404)(
        Quote.objects.select_related("quotee", "quoter"), number=number
    )
    return _quote_to_response(quote)


@router.post("/", response=QuoteResponse)
async def create_quote(request, payload: QuoteCreateRequest) -> QuoteResponse:
    """Create a new quote.

    Args:
        payload: Quote creation data
    """
    # Get or create members
    quotee, _ = await Member.objects.aget_or_create(
        username__iexact=payload.quotee_username.lower(),
        defaults={
            "username": payload.quotee_username.lower(),
            "display_name": payload.quotee_username,
        },
    )

    quoter, _ = await Member.objects.aget_or_create(
        username__iexact=payload.quoter_username.lower(),
        defaults={
            "username": payload.quoter_username.lower(),
            "display_name": payload.quoter_username,
        },
    )

    # Get next quote number
    last_quote = await Quote.objects.order_by("-number").afirst()
    next_number = (last_quote.number + 1) if last_quote else 1

    # Create quote
    quote = await Quote.objects.acreate(
        number=next_number,
        text=payload.text,
        quotee=quotee,
        quoter=quoter,
        year=datetime.now().year,
        created_at=timezone.now(),
    )

    await quote.arefresh_from_db()
    await sync_to_async(lambda: quote.quotee)()
    await sync_to_async(lambda: quote.quoter)()

    return _quote_to_response(quote)


@router.patch("/{number}", response=QuoteResponse)
async def update_quote(
    request, number: int, payload: QuoteUpdateRequest
) -> QuoteResponse:
    """Update a quote.

    Args:
        number: The quote number
        payload: Quote update data
    """
    quote = await sync_to_async(get_object_or_404)(
        Quote.objects.select_related("quotee", "quoter"), number=number
    )

    # Update fields if provided
    if payload.text is not None:
        quote.text = payload.text

    if payload.quotee_username is not None:
        quotee, _ = await Member.objects.aget_or_create(
            username__iexact=payload.quotee_username.lower(),
            defaults={
                "username": payload.quotee_username.lower(),
                "display_name": payload.quotee_username,
            },
        )
        quote.quotee = quotee

    if payload.quoter_username is not None:
        quoter, _ = await Member.objects.aget_or_create(
            username__iexact=payload.quoter_username.lower(),
            defaults={
                "username": payload.quoter_username.lower(),
                "display_name": payload.quoter_username,
            },
        )
        quote.quoter = quoter

    if payload.year is not None:
        quote.year = payload.year

    await sync_to_async(quote.save)()
    await quote.arefresh_from_db()
    await sync_to_async(lambda: quote.quotee)()
    await sync_to_async(lambda: quote.quoter)()

    return _quote_to_response(quote)


@router.delete("/{number}", response=dict)
async def delete_quote(request, number: int) -> dict:
    """Delete a quote.

    Args:
        number: The quote number
    """
    quote = await sync_to_async(get_object_or_404)(Quote, number=number)
    await sync_to_async(quote.delete)()

    return {"success": True, "message": f"Quote #{number} deleted"}
