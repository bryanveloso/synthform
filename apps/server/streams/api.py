"""Stream API endpoints."""

from __future__ import annotations

import logging

from ninja import Router

from .models import Status
from .schemas import StatusResponse

logger = logging.getLogger(__name__)
router = Router(tags=["streams"])


@router.get("/status/", response=StatusResponse)
async def get_status(request) -> StatusResponse:
    """Get current broadcaster status.

    Returns:
        Current status, message, and last updated time
    """
    status = await Status.objects.aget_or_create(
        defaults={"status": "online", "message": ""}
    )

    # aget_or_create returns a tuple (instance, created)
    status_instance = status[0] if isinstance(status, tuple) else status

    return StatusResponse(
        status=status_instance.status,
        message=status_instance.message,
        updated_at=status_instance.updated_at,
    )
