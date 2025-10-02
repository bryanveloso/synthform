from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as redis
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class EventConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for broadcasting events to overlay clients."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = None
        self.pubsub = None
        self.redis_task = None

    async def connect(self):
        """Accept WebSocket connection and start Redis subscription."""
        await self.accept()
        logger.info("[WebSocket] Overlay client connected.")

        # Connect to Redis
        from django.conf import settings

        self.redis = redis.from_url(settings.REDIS_URL)
        self.pubsub = self.redis.pubsub()

        # Subscribe to all event channels
        await self.pubsub.subscribe("events:twitch")
        logger.info("[WebSocket] Subscribed to Redis channel. channel=events:twitch")

        # Start Redis message listener
        self.redis_task = asyncio.create_task(self._listen_to_redis())

    async def disconnect(self, close_code):
        """Clean up Redis connections when client disconnects."""
        logger.info(f"[WebSocket] Overlay client disconnected. code={close_code}")

        # Cancel Redis listener task
        if self.redis_task:
            self.redis_task.cancel()
            try:
                await self.redis_task
            except asyncio.CancelledError:
                pass

        # Close Redis connections with proper error handling
        try:
            if self.pubsub:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()
        except Exception as e:
            logger.warning(
                f'[WebSocket] 🟡 Error closing Redis pubsub. error="{str(e)}"'
            )

        try:
            if self.redis:
                await self.redis.close()
        except Exception as e:
            logger.warning(
                f'[WebSocket] 🟡 Error closing Redis connection. error="{str(e)}"'
            )

    async def _listen_to_redis(self):
        """Listen for Redis pub/sub messages and broadcast to WebSocket."""
        try:
            while True:
                # Use blocking get_message with timeout to avoid busy waiting
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    try:
                        # Parse the Redis message
                        event_data = json.loads(message["data"])

                        # Send to WebSocket client
                        await self.send(text_data=json.dumps(event_data))

                        logger.debug(
                            f"[WebSocket] Broadcasted event to overlay client. event_type={event_data['event_type']}"
                        )

                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(
                            f'[WebSocket] ❌ Failed to process Redis message. error="{str(e)}"'
                        )
                    except Exception as e:
                        logger.error(
                            f'[WebSocket] ❌ Failed to broadcast message. error="{str(e)}"'
                        )
                        break

        except asyncio.CancelledError:
            logger.info("[WebSocket] Redis listener task cancelled.")
        except Exception as e:
            logger.error(f'[WebSocket] ❌ Error in Redis listener. error="{str(e)}"')

    async def receive(self, text_data):
        """Handle messages from WebSocket clients (if needed for control)."""
        try:
            data = json.loads(text_data)
            logger.debug(
                f"[WebSocket] Received message from overlay client. data={data}"
            )

            # Handle client messages if needed (e.g., for overlay control)
            # For now, just log them

        except json.JSONDecodeError:
            logger.warning(
                f'[WebSocket] 🟡 Received invalid JSON from overlay client. data="{text_data}"'
            )


class MusicAgentConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for music agents (Apple Music, etc.) to send updates."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = None
        self.agent_type = None

    async def connect(self):
        """Accept WebSocket connection from music agent."""
        await self.accept()
        logger.info("[WebSocket] Music agent connected.")

        # Connect to Redis for broadcasting
        from django.conf import settings

        self.redis = redis.from_url(settings.REDIS_URL)

    async def disconnect(self, close_code):
        """Clean up when agent disconnects."""
        logger.info(f"[WebSocket] Music agent disconnected. code={close_code}")

        if self.redis:
            await self.redis.close()

    async def receive(self, text_data):
        """Handle music updates from agents."""
        try:
            data = json.loads(text_data)

            # Identify agent type from first message or data
            if "agent_type" in data:
                self.agent_type = data["agent_type"]
                logger.info(
                    f"[WebSocket] Music agent identified. type={self.agent_type}"
                )
                return

            # Process music update
            from .services.music import music_service

            if data.get("source") == "apple" or self.agent_type == "apple":
                music_service.process_apple_music_update(data)
            elif data.get("source") == "rainwave" or self.agent_type == "rainwave":
                music_service.process_rainwave_update(data)
            else:
                logger.warning(
                    f"[WebSocket] 🟡 Unknown music source. source={data.get('source')}"
                )

        except json.JSONDecodeError:
            logger.warning(
                f'[WebSocket] 🟡 Received invalid JSON from music agent. data="{text_data}"'
            )
        except Exception as e:
            logger.error(
                f'[WebSocket] ❌ Failed to process music agent update. error="{str(e)}"'
            )
