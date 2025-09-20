from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC
from datetime import datetime

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
    preference: str | None = None
    collection: int = 0
    collection_total: int | None = None
    ascension: int = 0
    wins: int = 0
    esper: str = ""
    artifact: str = ""
    job: str = ""
    job_level: int = 0
    exp: int | None = None
    gil: int | None = None
    unit: str | None = None
    freehirecount: int = 0
    freehire_available: bool = False
    wins_until_freehire: int = 0
    jobap: int = 0
    artifact_bonuses: dict = {}
    job_slots: dict = {}
    job_bonuses: dict = {}
    card_passive: str = ""


class FFBotEvent(Schema):
    type: str = Field(
        ..., description="Event type: stats, hire, change, attack, join, save"
    )
    player: str | None = None
    timestamp: float | None = None
    data: FFBotStatsData | None = None
    # Hire event fields
    character: str | None = None
    cost: int | None = None
    # Change event fields
    from_: str | None = Field(None, alias="from")
    to: str | None = None
    # Attack event fields
    damage: int | None = None
    target: str | None = None
    # Save event fields
    player_count: int | None = None
    metadata: dict | None = None


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
        timestamp = data.get("timestamp", datetime.now(UTC).timestamp())

        logger.info(f"🎮 Processing FFBot {event_type} event from {player_username}")

        # Skip processing if missing required fields
        if not event_type:
            logger.warning("Invalid FFBot event: missing type")
            return

        # Handle events that don't require a player
        if event_type in NO_PLAYER_EVENTS:
            await publish_to_redis(event_type, None, data, timestamp)
            if event_type == "save":
                logger.info(f"FFBot auto-save: {data.get('player_count', 0)} players")
            else:
                logger.info(f"FFBot battle event: {event_type}")
            return

        # All other events require a player
        if not player_username:
            logger.warning(f"Invalid FFBot event: missing player for {event_type}")
            return

        # Get or create Member
        member = await get_or_create_member(player_username)

        # Get handler for event type or check if it's display-only
        player_stats = None
        handler = EVENT_HANDLERS.get(event_type)

        if handler:
            # Execute the appropriate update handler with error handling
            try:
                player_stats = await handler(member, data)
            except Exception as e:
                logger.error(f"Error in {event_type} handler: {e}", exc_info=True)
                # Try to get current stats as fallback
                try:
                    player_stats, _ = await Player.objects.aget_or_create(member=member)
                except Exception:
                    pass  # Continue without stats enrichment
        elif event_type in DISPLAY_ONLY_EVENTS:
            # Get current stats without updating
            player_stats, _ = await Player.objects.aget_or_create(member=member)
        else:
            logger.warning(f"Unknown FFBot event type: {event_type}")
            return

        # If we have player stats, enrich the payload with full data from database
        if player_stats:
            full_stats_data = {
                "lv": player_stats.lv,
                "atk": player_stats.atk,
                "mag": player_stats.mag,
                "spi": player_stats.spi,
                "hp": player_stats.hp,
                "exp": player_stats.exp,
                "gil": player_stats.gil,
                "collection": player_stats.collection,
                "collection_total": 100,  # This would need to come from game config
                "ascension": player_stats.ascension,
                "wins": player_stats.wins,
                "freehirecount": player_stats.freehirecount,
                "freehire_available": player_stats.freehirecount > 49,
                "wins_until_freehire": max(0, 50 - player_stats.freehirecount),
                "season": player_stats.season,
                "unit": player_stats.unit,
                "esper": player_stats.esper,
                "preference": player_stats.preferedstat,
                "job": player_stats.m1,
                "job_level": player_stats.jobap,
                "jobap": player_stats.jobap,
                "card": player_stats.card,
                "card_passive": player_stats.card_passive,
                "artifact": player_stats.card,  # artifact maps to card field
                "artifact_bonuses": {
                    "hp": player_stats.arti_hp,
                    "atk": player_stats.arti_atk,
                    "mag": player_stats.arti_mag,
                    "spi": player_stats.arti_spi,
                },
                "job_slots": {
                    "m1": player_stats.m1 or "",
                    "m2": player_stats.m2 or "",
                    "m3": player_stats.m3 or "",
                    "m4": player_stats.m4 or "",
                    "m5": player_stats.m5 or "",
                    "m6": player_stats.m6 or "",
                    "m7": player_stats.m7 or "",
                },
                "job_bonuses": {
                    "hp": player_stats.job_hp,
                    "atk": player_stats.job_atk,
                    "mag": player_stats.job_mag,
                    "spi": player_stats.job_spi,
                },
            }

            # For stats events, the game sends data under 'data' field
            # For hire/change events, enrich the root-level data
            if event_type == "stats":
                # Merge with game data (game data takes precedence for fields it sends)
                data["data"] = {**full_stats_data, **data.get("data", {})}
            else:
                # For hire/change events, add the full stats alongside the event-specific fields
                data["stats"] = full_stats_data

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


async def update_player_stats(member, stats_data: dict):
    """Update PlayerStats with latest data from stats event.

    Note: The game doesn't send exp, gil, freehirecount, or season in stats events.
    These are managed internally by the game and only gil is deducted during hire events.

    Returns the Player object so we can access additional fields like unit.
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
        "unit",
        "exp",
        "gil",
        "freehirecount",
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

    # Card passive
    if "card_passive" in stats_data:
        stats.card_passive = stats_data["card_passive"]
        fields_to_update.append("card_passive")

    # Handle artifact bonuses if sent
    if "artifact_bonuses" in stats_data:
        bonuses = stats_data["artifact_bonuses"]
        if "hp" in bonuses:
            stats.arti_hp = bonuses["hp"]
            fields_to_update.append("arti_hp")
        if "atk" in bonuses:
            stats.arti_atk = bonuses["atk"]
            fields_to_update.append("arti_atk")
        if "mag" in bonuses:
            stats.arti_mag = bonuses["mag"]
            fields_to_update.append("arti_mag")
        if "spi" in bonuses:
            stats.arti_spi = bonuses["spi"]
            fields_to_update.append("arti_spi")

    # Handle job bonuses if sent
    if "job_bonuses" in stats_data:
        bonuses = stats_data["job_bonuses"]
        if "hp" in bonuses:
            stats.job_hp = bonuses["hp"]
            fields_to_update.append("job_hp")
        if "atk" in bonuses:
            stats.job_atk = bonuses["atk"]
            fields_to_update.append("job_atk")
        if "mag" in bonuses:
            stats.job_mag = bonuses["mag"]
            fields_to_update.append("job_mag")
        if "spi" in bonuses:
            stats.job_spi = bonuses["spi"]
            fields_to_update.append("job_spi")

    # Handle job slots if sent
    if "job_slots" in stats_data:
        slots = stats_data["job_slots"]
        for i in range(1, 8):
            slot_key = f"m{i}"
            if slot_key in slots:
                setattr(stats, slot_key, slots[slot_key])
                fields_to_update.append(slot_key)

    if fields_to_update:
        fields_to_update.append("updated_at")
        await stats.asave(update_fields=fields_to_update)
        logger.debug(f"Updated Player stats for {member.display_name}")

    return stats


async def update_after_hire(member, hire_data: dict):
    """Update PlayerStats after a hire event.

    Note: Hired characters go into the collection, they don't become the current unit.
    Only !change updates the current unit.

    Returns the Player object so we can access all fields for payload enrichment.
    """
    stats, _ = await Player.objects.aget_or_create(member=member)

    fields_to_update = []

    # Reduce gil by cost if provided
    if "cost" in hire_data:
        stats.gil = max(0, stats.gil - hire_data["cost"])
        fields_to_update.append("gil")

    if fields_to_update:
        fields_to_update.append("updated_at")
        await stats.asave(update_fields=fields_to_update)

    return stats


async def update_after_change(member, change_data: dict):
    """Update PlayerStats after a character change event.

    Returns the Player object so we can access all fields for payload enrichment.
    """
    stats, _ = await Player.objects.aget_or_create(member=member)

    if "to" in change_data:
        stats.unit = change_data["to"]
        await stats.asave(update_fields=["unit", "updated_at"])

    return stats


async def publish_to_redis(
    event_type: str, member, data: dict, timestamp: float
) -> None:
    """Forward all events to Redis for real-time display."""
    redis_client = None
    try:
        redis_client = redis.from_url(settings.REDIS_URL)

        # Build payload based on event type
        # For stats events, data is in data["data"]
        # For hire/change events, we have the raw event data plus enriched stats in data["stats"]
        if event_type == "stats":
            payload = data.get("data", {})
        elif event_type in ["hire", "change"]:
            # Include both the event-specific fields and the enriched stats
            payload = {
                k: v for k, v in data.items() if k not in ["type", "player", "stats"]
            }
            payload["stats"] = data.get("stats", {})
        else:
            # For other events, just pass through the data
            payload = data

        redis_message = {
            "event_type": f"ffbot.{event_type}",
            "source": "ffbot",
            "timestamp": datetime.fromtimestamp(timestamp, tz=UTC).isoformat(),
            "payload": payload,
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


async def update_after_preference(member, event_data: dict):
    """Update player's stat preference."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    preference = event_data.get("preference", "none")
    if preference:
        stats.preferedstat = preference
        await stats.asave(update_fields=["preferedstat", "updated_at"])

    return stats


async def update_after_ascension(member, event_data: dict):
    """Update player stats after ascension confirmation."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    # Ascension resets level and experience but increments ascension count
    stats.ascension = event_data.get("ascension", stats.ascension + 1)
    stats.lv = 1
    stats.exp = 1
    stats.wins = 0

    await stats.asave(update_fields=["ascension", "lv", "exp", "wins", "updated_at"])

    return stats


async def update_after_esper(member, event_data: dict):
    """Update player's equipped esper."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    esper = event_data.get("esper", "")
    if esper:
        stats.esper = esper
        await stats.asave(update_fields=["esper", "updated_at"])

    return stats


async def update_after_artifact(member, event_data: dict):
    """Update player's artifact and bonuses."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    artifact = event_data.get("artifact", "")
    bonuses = event_data.get("bonuses", {})

    if artifact:
        stats.card = artifact  # artifact maps to card field

    # Update artifact bonuses
    if bonuses:
        stats.arti_hp = bonuses.get("hp", 0)
        stats.arti_atk = bonuses.get("atk", 0)
        stats.arti_mag = bonuses.get("mag", 0)
        stats.arti_spi = bonuses.get("spi", 0)

    fields_to_update = [
        "card",
        "arti_hp",
        "arti_atk",
        "arti_mag",
        "arti_spi",
        "updated_at",
    ]
    await stats.asave(update_fields=fields_to_update)

    return stats


async def update_after_job(member, event_data: dict):
    """Update player's main job."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    job = event_data.get("job", "")
    if job:
        stats.m1 = job
        stats.jobap = 0  # Reset job AP when changing jobs
        await stats.asave(update_fields=["m1", "jobap", "updated_at"])

    return stats


async def update_after_card(member, event_data: dict):
    """Update player's card and passive."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    card = event_data.get("card", "")
    passive = event_data.get("passive", "")

    if card:
        stats.card = card
    if passive:
        stats.card_passive = passive

    await stats.asave(update_fields=["card", "card_passive", "updated_at"])

    return stats


async def update_after_mastery(member, event_data: dict):
    """Update player's mastery slots."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    slot = event_data.get("slot", "")
    job = event_data.get("job", "")
    success = event_data.get("success", False)

    # Only update if the mastery was successful
    if success and slot and job:
        # Map slot names to model fields
        slot_mapping = {
            "m2": "m2",
            "m3": "m3",
            "m4": "m4",
            "m5": "m5",
            "m6": "m6",
            "m7": "m7",
        }

        field_name = slot_mapping.get(slot)
        if field_name:
            setattr(stats, field_name, job)
            await stats.asave(update_fields=[field_name, "updated_at"])

    return stats


async def update_after_freehire(member, event_data: dict):
    """Update player after free hire."""
    stats, _ = await Player.objects.aget_or_create(member=member)

    available = event_data.get("available", False)

    # If free hire was used, reset the counter
    if available:
        stats.freehirecount = 0
        await stats.asave(update_fields=["freehirecount", "updated_at"])

    return stats


# Event handler mapping - cleaner than giant if/elif chain
EVENT_HANDLERS = {
    # Database update events
    "stats": lambda m, d: update_player_stats(m, d.get("data", {})),
    "hire": update_after_hire,
    "change": update_after_change,
    "preference": update_after_preference,
    "ascension_confirm": update_after_ascension,
    "esper": update_after_esper,
    "artifact": update_after_artifact,
    "job": update_after_job,
    "card": update_after_card,
    "mastery": update_after_mastery,
    "freehire": update_after_freehire,
}

# Events that don't require a player
NO_PLAYER_EVENTS = {"save", "party_wipe", "new_run", "battle_victory"}

# Display-only events (get stats but don't update)
DISPLAY_ONLY_EVENTS = {"ascension_preview", "missing", "attack", "join"}
