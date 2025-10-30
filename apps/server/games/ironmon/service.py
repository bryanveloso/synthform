from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as redis
from asgiref.sync import sync_to_async
from django.conf import settings

from .models import Challenge
from .models import Checkpoint
from .models import Result
from .models import Seed

logger = logging.getLogger(__name__)

# Game enumeration matching IronMON Connect plugin
GAMES = {
    1: "Ruby/Sapphire",
    2: "Emerald",
    3: "FireRed/LeafGreen",
}


class IronMONService:
    """
    Service for receiving IronMON Connect plugin messages.

    Listens on port 8080 for length-prefixed JSON messages in format: "LENGTH MESSAGE"
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.server = None
        self.redis_client = None
        self.current_seed_id = None
        self.current_challenge_id = None

        # State tracking
        self._game = {}
        self._seed = None
        self._team = []
        self._items = []
        self._stats = {}
        self._location_id = None
        self._battle = None
        self._checkpoints_cleared = []

    async def start(self):
        """Start the TCP server and connect to Redis."""
        self.redis_client = await redis.from_url(settings.REDIS_URL)
        logger.info(f"[IronMON] Connected to Redis")

        # Restore state from Redis
        await self._restore_state()

        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )

        addr = self.server.sockets[0].getsockname()
        logger.info(f"[IronMON] TCP server listening on {addr[0]}:{addr[1]}")

        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        """Stop the TCP server and close Redis connection."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        if self.redis_client:
            await self.redis_client.aclose()

        logger.info("[IronMON] TCP server stopped")

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle a new client connection."""
        addr = writer.get_extra_info("peername")
        logger.info(f"[IronMON] Client connected from {addr}")

        buffer = b""

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break

                buffer += data

                # Process all complete messages in the buffer
                buffer = await self.process_buffer(buffer)

        except Exception as e:
            logger.error(f"[IronMON] Error handling client: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"[IronMON] Client disconnected from {addr}")

    async def process_buffer(self, buffer: bytes) -> bytes:
        """Process all complete messages in the buffer."""
        while buffer:
            # Try to parse a message
            try:
                # Find the space separating length from message
                space_idx = buffer.find(b" ")
                if space_idx == -1:
                    # No space found yet, need more data
                    break

                # Parse the length
                length_str = buffer[:space_idx].decode("utf-8")
                message_length = int(length_str)

                # Check if we have the complete message
                message_start = space_idx + 1
                message_end = message_start + message_length

                if len(buffer) < message_end:
                    # Don't have complete message yet
                    break

                # Extract the message
                message_bytes = buffer[message_start:message_end]
                message_str = message_bytes.decode("utf-8")

                # Process the message
                await self.process_message(message_str)

                # Remove processed message from buffer
                buffer = buffer[message_end:]

            except (ValueError, UnicodeDecodeError) as e:
                logger.error(f"[IronMON] Error parsing message: {e}")
                # Skip invalid data
                buffer = buffer[1:]

        return buffer

    async def _restore_state(self):
        """Restore state from Redis."""
        try:
            state_json = await self.redis_client.get("ironmon:current_state")
            if not state_json:
                logger.debug("[IronMON] No persisted state found")
                return

            state = json.loads(state_json)
            self._game = state.get("game", {})
            self._seed = state.get("seed")
            self._team = state.get("team", [])
            self._items = state.get("items", [])
            self._stats = state.get("stats", {})
            self._location_id = state.get("location_id")
            self._battle = state.get("battle")
            self._checkpoints_cleared = state.get("checkpoints_cleared", [])

            logger.info("[IronMON] State restored from Redis")
        except Exception as e:
            logger.error(f"[IronMON] Failed to restore state: {e}")

    async def _persist_state(self):
        """Persist current state to Redis."""
        try:
            state = {
                "game": self._game,
                "seed": self._seed,
                "team": self._team,
                "items": self._items,
                "stats": self._stats,
                "location_id": self._location_id,
                "battle": self._battle,
                "checkpoints_cleared": self._checkpoints_cleared,
            }
            await self.redis_client.set("ironmon:current_state", json.dumps(state))
        except Exception as e:
            logger.error(f"[IronMON] Failed to persist state: {e}")

    async def get_current_state(self) -> dict[str, Any]:
        """Get current run state."""
        return {
            "game": self._game,
            "seed": self._seed,
            "team": self._team,
            "items": self._items,
            "stats": self._stats,
            "location_id": self._location_id,
            "battle": self._battle,
            "checkpoints_cleared": self._checkpoints_cleared,
        }

    async def process_message(self, message_str: str):
        """Process a single IronMON message."""
        try:
            data = json.loads(message_str)
            message_type = data.get("type")

            if not message_type:
                logger.warning("[IronMON] Message missing type field")
                return

            # Extract metadata/data (plugin uses both formats)
            metadata = data.get("data") or data.get("metadata")
            if not metadata:
                logger.warning(
                    f"[IronMON] Message missing data/metadata: {message_type}"
                )
                return

            logger.debug(f"[IronMON] Received {message_type} message")

            # Handle message based on type
            if message_type == "init":
                await self.handle_init(metadata)
            elif message_type == "seed":
                await self.handle_seed(metadata)
            elif message_type == "checkpoint":
                await self.handle_checkpoint(metadata)
            elif message_type == "location":
                await self.handle_location(metadata)
            elif message_type == "battle_started":
                await self.handle_battle_started(metadata)
            elif message_type == "battle_ended":
                await self.handle_battle_ended(metadata)
            elif message_type == "team_update":
                await self.handle_team_update(metadata)
            elif message_type == "item_usage":
                await self.handle_item_usage(metadata)
            elif message_type == "healing_summary":
                await self.handle_healing_summary(metadata)
            elif message_type == "error":
                await self.handle_error(metadata)
            elif message_type == "heartbeat":
                # Don't log heartbeats
                pass
            else:
                logger.warning(f"[IronMON] Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"[IronMON] Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"[IronMON] Error processing message: {e}", exc_info=True)

    async def handle_init(self, metadata: dict[str, Any]):
        """Handle game initialization message."""
        version = metadata.get("version")
        game_id = metadata.get("game")
        game_name = GAMES.get(game_id, "Unknown")

        logger.info(f"[IronMON] Game initialized: {game_name} v{version}")

        # Update state
        self._game = {
            "version": version,
            "name": game_name,
            "id": game_id,
        }
        await self._persist_state()

        await self.publish_event(
            "ironmon.init",
            {
                "version": version,
                "game": game_name,
                "game_id": game_id,
            },
        )

    async def handle_seed(self, metadata: dict[str, Any]):
        """Handle new seed (run attempt) message."""
        seed_count = metadata.get("attempt") or metadata.get("count")
        if not seed_count:
            logger.warning(f"[IronMON] Seed message missing attempt/count. metadata={metadata}")
            return

        logger.info(f"[IronMON] New attempt started: Attempt #{seed_count}")

        # Get or create the first challenge (we'll seed this data separately)
        challenge = await sync_to_async(Challenge.objects.first)()
        if not challenge:
            logger.error("[IronMON] No challenges found in database")
            return

        self.current_challenge_id = challenge.id
        self.current_seed_id = seed_count

        # Create seed record
        seed, created = await sync_to_async(Seed.objects.get_or_create)(
            id=seed_count, defaults={"challenge_id": challenge.id}
        )

        if created:
            logger.info(f"[IronMON] Created seed #{seed_count} for {challenge.name}")
        else:
            logger.debug(f"[IronMON] Seed #{seed_count} already exists")

        # Reset run-specific state
        self._seed = {
            "id": seed_count,
            "challenge_id": challenge.id,
            "challenge_name": challenge.name,
        }
        self._team = []
        self._items = []
        self._stats = {}
        self._location_id = None
        self._battle = None
        self._checkpoints_cleared = []
        await self._persist_state()

        await self.publish_event(
            "ironmon.seed",
            {
                "seed_id": seed_count,
                "challenge_id": challenge.id,
                "challenge_name": challenge.name,
            },
        )

    async def handle_checkpoint(self, metadata: dict[str, Any]):
        """Handle checkpoint cleared message."""
        checkpoint_id = metadata.get("id")
        checkpoint_name = metadata.get("name")

        if not checkpoint_name:
            logger.warning("[IronMON] Checkpoint message missing name")
            return

        logger.info(f"[IronMON] Checkpoint cleared: {checkpoint_name}")

        if not self.current_seed_id:
            logger.warning("[IronMON] Received checkpoint but no active seed")
            return

        # Find the checkpoint
        checkpoint = await sync_to_async(
            Checkpoint.objects.filter(name=checkpoint_name).first
        )()

        if not checkpoint:
            logger.error(f"[IronMON] Checkpoint not found: {checkpoint_name}")
            return

        # Record the result (always True since we only get notified on clears)
        result, created = await sync_to_async(Result.objects.get_or_create)(
            seed_id=self.current_seed_id,
            checkpoint_id=checkpoint.id,
            defaults={"result": True},
        )

        if created:
            logger.info(f"[IronMON] Recorded checkpoint clear: {checkpoint_name}")
        else:
            logger.debug(f"[IronMON] Checkpoint result already recorded")

        # Update state
        self._checkpoints_cleared.append(
            {
                "id": checkpoint.id,
                "name": checkpoint_name,
                "trainer": checkpoint.trainer,
                "order": checkpoint.order,
            }
        )
        await self._persist_state()

        await self.publish_event(
            "ironmon.checkpoint",
            {
                "seed_id": self.current_seed_id,
                "checkpoint_id": checkpoint.id,
                "checkpoint_name": checkpoint_name,
                "trainer": checkpoint.trainer,
                "order": checkpoint.order,
            },
        )

    async def handle_location(self, metadata: dict[str, Any]):
        """Handle location change message."""
        location_id = metadata.get("mapId")
        location_name = metadata.get("name")
        logger.debug(f"[IronMON] Location changed: {location_name} (ID: {location_id})")

        # Update state
        self._location_id = location_id
        await self._persist_state()

        await self.publish_event(
            "ironmon.location",
            {
                "location_id": location_id,
                "location_name": location_name,
            },
        )

    async def handle_battle_started(self, metadata: dict[str, Any]):
        """Handle battle_started message."""
        is_wild = metadata.get("isWild", False)
        trainer = metadata.get("trainer", {})
        opponent = metadata.get("opponent", {})

        battle_type = "Wild" if is_wild else trainer.get("name", "Trainer")
        logger.info(f"[IronMON] Battle started: {battle_type}")

        # Update state
        self._battle = {
            "active": True,
            "is_wild": is_wild,
            "trainer": trainer,
            "opponent": opponent,
            "result": None,
        }
        await self._persist_state()

        await self.publish_event(
            "ironmon.battle_start",
            {
                "is_wild": is_wild,
                "trainer": trainer,
                "opponent": opponent,
            },
        )

    async def handle_battle_ended(self, metadata: dict[str, Any]):
        """Handle battle_ended message."""
        player_won = metadata.get("playerWon", False)
        duration = metadata.get("duration", 0)

        result = "Won" if player_won else "Lost"
        logger.info(f"[IronMON] Battle ended: {result}")

        # Update state
        if self._battle:
            self._battle["active"] = False
            self._battle["player_won"] = player_won
            self._battle["duration"] = duration
        await self._persist_state()

        await self.publish_event(
            "ironmon.battle_end",
            {
                "player_won": player_won,
                "duration": duration,
            },
        )

    async def handle_team_update(self, metadata: dict[str, Any]):
        """Handle team_update message."""
        slot = metadata.get("slot")
        pokemon = metadata.get("pokemon", {})
        logger.debug(f"[IronMON] Team updated: Slot {slot} - {pokemon.get('name', 'Unknown')}")

        # Update state - update specific slot
        if slot and 1 <= slot <= 6:
            while len(self._team) < slot:
                self._team.append(None)
            self._team[slot - 1] = pokemon
        await self._persist_state()

        await self.publish_event(
            "ironmon.team_update",
            {
                "slot": slot,
                "pokemon": pokemon,
            },
        )

    async def handle_item_usage(self, metadata: dict[str, Any]):
        """Handle item_usage message."""
        item = metadata.get("item", {})
        action = metadata.get("action")
        context = metadata.get("context")
        logger.debug(f"[IronMON] Item {action}: {item.get('name', 'Unknown')} in {context}")

        # Update state
        if action == "used":
            # Remove from inventory
            pass
        elif action == "gained":
            # Add to inventory
            pass
        await self._persist_state()

        await self.publish_event(
            "ironmon.item_usage",
            {
                "item": item,
                "action": action,
                "context": context,
            },
        )

    async def handle_healing_summary(self, metadata: dict[str, Any]):
        """Handle healing_summary message."""
        total_healing = metadata.get("totalHealing", 0)
        healing_percentage = metadata.get("healingPercentage", 0)
        logger.debug(f"[IronMON] Healing: {total_healing} HP ({healing_percentage}%)")

        # Update state
        self._stats["healing"] = {
            "total_healing": total_healing,
            "healing_percentage": healing_percentage,
        }
        await self._persist_state()

        await self.publish_event(
            "ironmon.healing_summary",
            {
                "total_healing": total_healing,
                "healing_percentage": healing_percentage,
            },
        )

    async def handle_error(self, metadata: dict[str, Any]):
        """Handle error message from plugin."""
        code = metadata.get("code")
        message = metadata.get("message")

        logger.warning(f"[IronMON] Plugin error: {code} - {message}")

        await self.publish_event(
            "ironmon.error",
            {
                "code": code,
                "message": message,
            },
        )

    async def publish_event(self, event_type: str, data: dict[str, Any]):
        """Publish event to Redis for WebSocket consumers."""
        if not self.redis_client:
            return

        event = {
            "event_type": event_type,
            "source": "ironmon",
            "data": data,
        }

        try:
            await self.redis_client.publish("events:games:ironmon", json.dumps(event))
        except Exception as e:
            logger.error(f"[IronMON] Failed to publish event: {e}")
