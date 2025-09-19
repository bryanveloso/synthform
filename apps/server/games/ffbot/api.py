from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from datetime import timezone
from typing import Optional

import redis.asyncio as redis
from django.conf import settings
from ninja import NinjaAPI
from ninja import Schema
from pydantic import Field

from events.models import Member
from games.ffbot.models import Player

logger = logging.getLogger(__name__)

# Create the FFBot API
api = NinjaAPI(urls_namespace="ffbot", csrf=False)


# Pydantic schemas for request/response validation
class FFBotStatsData(Schema):
    lv: int = 1
    atk: int = 0
    mag: int = 0
    spi: int = 0
    hp: int = 0
    preference: Optional[str] = None
    collection: int = 0
    collection_total: Optional[int] = None
    ascension: int = 0
    wins: int = 0
    esper: str = ""
    artifact: str = ""
    job: str = ""
    job_level: int = 0
    exp: Optional[int] = None
    gil: Optional[int] = None


class FFBotEvent(Schema):
    type: str = Field(
        ..., description="Event type: stats, hire, change, attack, join, save"
    )
    player: Optional[str] = None
    timestamp: Optional[float] = None
    data: Optional[FFBotStatsData] = None
    # Hire event fields
    character: Optional[str] = None
    cost: Optional[int] = None
    # Change event fields
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    # Attack event fields
    damage: Optional[int] = None
    target: Optional[str] = None
    # Save event fields
    player_count: Optional[int] = None
    metadata: Optional[dict] = None


class AcceptedResponse(Schema):
    status: str = "accepted"


@api.post(
    "/ffbot", response={202: AcceptedResponse}, summary="Receive FFBot game events"
)
async def ffbot_event(request, event: FFBotEvent):
    """
    Receives FFBot game events and returns 202 immediately.
    Processing happens asynchronously in the background.
    """
    # Queue for async processing
    asyncio.create_task(process_ffbot_event(event.dict()))

    # Return 202 Accepted immediately
    return 202, {"status": "accepted"}


async def process_ffbot_event(data: dict) -> None:
    """Process FFBot event asynchronously."""
    try:
        event_type = data.get("type")
        player_username = data.get("player")
        timestamp = data.get("timestamp", datetime.now(timezone.utc).timestamp())

        logger.info(f"🎮 Processing FFBot {event_type} event from {player_username}")

        # Skip processing if missing required fields
        if not event_type:
            logger.warning("Invalid FFBot event: missing type")
            return

        # For save events, just log and publish to Redis
        if event_type == "save":
            await publish_to_redis("save", None, data, timestamp)
            logger.info(f"FFBot auto-save: {data.get('player_count', 0)} players")
            return

        # All other events require a player
        if not player_username:
            logger.warning(f"Invalid FFBot event: missing player for {event_type}")
            return

        # Get or create Member
        member = await get_or_create_member(player_username)

        # Update PlayerStats cache for events with stats data
        if event_type == "stats":
            await update_player_stats(member, data.get("data", {}))
        elif event_type == "hire":
            await update_after_hire(member, data)
        elif event_type == "change":
            await update_after_change(member, data)

        # Always forward to Redis for real-time overlay
        await publish_to_redis(event_type, member, data, timestamp)

        logger.debug(f"✅ Processed FFBot {event_type} event from {player_username}")

    except Exception as e:
        logger.error(f"Error processing FFBot event: {e}", exc_info=True)


async def get_or_create_member(username: str):
    """Get or create Member by username."""
    username_lower = username.lower()

    member, created = await Member.objects.aget_or_create(
        username=username_lower, defaults={"display_name": username}
    )

    if created:
        logger.info(f"Created new Member for FFBot player: {username}")

    return member


async def update_player_stats(member, stats_data: dict) -> None:
    """Update PlayerStats with latest data from stats event.

    Note: The game doesn't send exp, gil, freehirecount, or season in stats events.
    These are managed internally by the game and only gil is deducted during hire events.
    """
    stats, created = await Player.objects.aget_or_create(member=member)

    fields_to_update = []

    # Core stats - only update fields that are actually sent
    for field in [
        "lv",
        "atk",
        "mag",
        "spi",
        "hp",
        "collection",
        "ascension",
        "wins",
        "esper",
    ]:
        if field in stats_data and stats_data[field] is not None:
            setattr(stats, field, stats_data[field])
            fields_to_update.append(field)

    # Handle preference field name difference
    if "preference" in stats_data:
        stats.preferedstat = stats_data["preference"]
        fields_to_update.append("preferedstat")

    # Job fields
    if "job" in stats_data and stats_data["job"]:
        stats.m1 = stats_data["job"]
        fields_to_update.append("m1")
    if "job_level" in stats_data:
        stats.jobap = stats_data["job_level"]
        fields_to_update.append("jobap")

    # Card/artifact fields (artifact maps to card)
    if "artifact" in stats_data:
        stats.card = stats_data["artifact"]
        fields_to_update.append("card")

    if fields_to_update:
        fields_to_update.append("updated_at")
        await stats.asave(update_fields=fields_to_update)
        logger.debug(f"Updated Player stats for {member.display_name}")


async def update_after_hire(member, hire_data: dict) -> None:
    """Update PlayerStats after a hire event."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    fields_to_update = []

    # Update unit if character provided
    if "character" in hire_data:
        stats.unit = hire_data["character"]
        fields_to_update.append("unit")

    # Reduce gil by cost if provided
    if "cost" in hire_data:
        stats.gil = max(0, stats.gil - hire_data["cost"])
        fields_to_update.append("gil")

    if fields_to_update:
        fields_to_update.append("updated_at")
        await stats.asave(update_fields=fields_to_update)


async def update_after_change(member, change_data: dict) -> None:
    """Update PlayerStats after a character change event."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    if "to" in change_data:
        stats.unit = change_data["to"]
        await stats.asave(update_fields=["unit", "updated_at"])


async def publish_to_redis(
    event_type: str, member, data: dict, timestamp: float
) -> None:
    """Forward all events to Redis for real-time display."""
    redis_client = None
    try:
        redis_client = redis.from_url(settings.REDIS_URL)

        redis_message = {
            "event_type": f"ffbot.{event_type}",
            "source": "ffbot",
            "timestamp": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
            "payload": data.get("data", {}),
            "player": data.get("player"),
        }

        # Add member info if available
        if member:
            redis_message["member"] = {
                "id": str(member.id),
                "username": member.username,
                "display_name": member.display_name,
            }

        await redis_client.publish("events:games:ffbot", json.dumps(redis_message))
        logger.debug(
            f"Published FFBot {event_type} to Redis channel events:games:ffbot"
        )

    except Exception as e:
        logger.error(f"Error publishing to Redis: {e}")
    finally:
        if redis_client:
            await redis_client.close()
