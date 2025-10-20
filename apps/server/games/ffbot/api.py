from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC
from datetime import datetime

import redis.asyncio as redis
from django.conf import settings
from ninja import Router
from ninja import Schema
from pydantic import Field

from events.models import Member
from games.ffbot.models import Player

logger = logging.getLogger(__name__)

# Create the FFBot Router
router = Router(tags=["ffbot"])

# Track background tasks to prevent garbage collection
_background_tasks = set()


def _create_background_task(coro):
    """Create a background task with proper exception handling."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


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
    job: str = ""
    job_level: int = 0
    exp: int | None = None
    gil: int | None = None
    unit: str | None = None
    freehirecount: int = 0
    freehire_available: bool = False
    wins_until_freehire: int = 0
    jobap: int = 0
    job_slots: dict = {}
    job_bonuses: dict = {}
    card: str = ""
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


@router.post("/", response={202: AcceptedResponse}, summary="Receive FFBot game events")
async def ffbot_event(request, event: FFBotEvent):
    """
    Receives FFBot game events and returns 202 immediately.
    Processing happens asynchronously in the background.
    """
    # Queue for async processing
    _create_background_task(process_ffbot_event(event.dict()))

    # Return 202 Accepted immediately
    return 202, {"status": "accepted"}


@router.get("/players/{username}", summary="Get player stats by username")
async def get_player_stats(request, username: str):
    """
    Get FFBot player stats by username.
    Returns 404 if player not found.
    """
    try:
        # Get member by username (case-insensitive)
        member = await Member.objects.filter(username__iexact=username).afirst()

        if not member:
            # Try display_name as fallback
            member = await Member.objects.filter(display_name__iexact=username).afirst()

        if not member:
            return 404, {"error": "Player not found"}

        # Get player stats
        try:
            player = await Player.objects.select_related("member").aget(member=member)
        except Player.DoesNotExist:
            return 404, {"error": "No stats found for this player"}

        # Build response matching what the bot expects
        response = {
            "player": username,
            "member": {
                "id": str(member.id),
                "username": member.username,
                "display_name": member.display_name,
            },
            "data": {
                "lv": player.lv,
                "atk": player.atk,
                "mag": player.mag,
                "spi": player.spi,
                "hp": player.hp,
                "gil": player.gil,
                "exp": player.exp,
                "collection": player.collection,
                "ascension": player.ascension,
                "wins": player.wins,
                "unit": player.unit,
                "esper": player.esper,
                "preference": player.preferedstat,
                "freehirecount": player.freehirecount,
                "freehire_available": player.freehirecount >= 50,
                "job": player.m1,
                "job_level": player.jobap,
                "job_slots": {
                    "m1": player.m1 or "",
                    "m2": player.m2 or "",
                    "m3": player.m3 or "",
                    "m4": player.m4 or "",
                    "m5": player.m5 or "",
                    "m6": player.m6 or "",
                    "m7": player.m7 or "",
                },
                "job_bonuses": {
                    "hp": player.job_hp,
                    "atk": player.job_atk,
                    "mag": player.job_mag,
                    "spi": player.job_spi,
                },
                "card": player.card,
                "card_passive": player.card_passive,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return response
    except Exception as e:
        logger.error(
            f'[FFBot] Error fetching player stats. username={username} error="{str(e)}"',
            exc_info=True,
        )
        return 500, {"error": "Internal server error"}


async def process_ffbot_event(data: dict) -> None:
    """Process FFBot event asynchronously."""
    try:
        event_type = data.get("type")
        player_username = data.get("player")
        timestamp = data.get("timestamp", datetime.now(UTC).timestamp())

        logger.info(
            f"[FFBot] 🎮 Processing event. event_type={event_type} player={player_username}"
        )

        # Skip processing if missing required fields
        if not event_type:
            logger.warning("[FFBot] Invalid event. reason=missing_type")
            return

        # Handle events that don't require a player
        if event_type in NO_PLAYER_EVENTS:
            await publish_to_redis(event_type, None, data, timestamp)
            if event_type == "save":
                logger.info(
                    f"[FFBot] Auto-save event. player_count={data.get('player_count', 0)}"
                )
            else:
                logger.info(f"[FFBot] Battle event. event_type={event_type}")
            return

        # All other events require a player
        if not player_username:
            logger.warning(
                f"[FFBot] Invalid event. reason=missing_player event_type={event_type}"
            )
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
                logger.error(
                    f'[FFBot] Error in event handler. event_type={event_type} error="{str(e)}"',
                    exc_info=True,
                )
                # Try to get current stats as fallback
                try:
                    player_stats, _ = await Player.objects.aget_or_create(member=member)
                except Exception:
                    pass  # Continue without stats enrichment
        elif event_type in DISPLAY_ONLY_EVENTS:
            # Get current stats without updating
            player_stats, _ = await Player.objects.aget_or_create(member=member)
        else:
            logger.warning(f"[FFBot] Unknown event type. event_type={event_type}")
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
                    "hp": getattr(player_stats, "job_hp", 0),
                    "atk": getattr(player_stats, "job_atk", 0),
                    "mag": getattr(player_stats, "job_mag", 0),
                    "spi": getattr(player_stats, "job_spi", 0),
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

        logger.debug(
            f"[FFBot] ✅ Event processed. event_type={event_type} player={player_username}"
        )

    except Exception as e:
        logger.error(f'[FFBot] Error processing event. error="{str(e)}"', exc_info=True)


async def get_or_create_member(username: str):
    """Get or create Member by username."""
    username_lower = username.lower()

    member, created = await Member.objects.aget_or_create(
        username=username_lower, defaults={"display_name": username}
    )

    if created:
        logger.info(f"[FFBot] Created new Member. username={username}")

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

    # Card field
    if "card" in stats_data:
        stats.card = stats_data["card"]
        fields_to_update.append("card")

    # Card passive
    if "card_passive" in stats_data:
        stats.card_passive = stats_data["card_passive"]
        fields_to_update.append("card_passive")

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
        logger.debug(f"[FFBot] Updated Player stats. player={member.display_name}")

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
        logger.debug(f"[FFBot] Published to Redis. event_type={event_type}")

    except Exception as e:
        logger.warning(f'[FFBot] Error publishing to Redis. error="{str(e)}"')
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


# Artifact handler removed - artifacts are from a previous season and no longer used


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
    "job": update_after_job,
    "card": update_after_card,
    "mastery": update_after_mastery,
    "freehire": update_after_freehire,
}

# Events that don't require a player
NO_PLAYER_EVENTS = {"save", "party_wipe", "new_run", "battle_victory"}

# Display-only events (get stats but don't update)
DISPLAY_ONLY_EVENTS = {"ascension_preview", "missing", "attack", "join", "artifact"}
