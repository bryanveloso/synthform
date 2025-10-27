"""Stream API schemas."""

from __future__ import annotations

from datetime import datetime

from ninja import Schema


class StatusResponse(Schema):
    """Response schema for current status."""

    status: str
    message: str
    updated_at: datetime
