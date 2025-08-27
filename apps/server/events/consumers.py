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
        logger.info("Overlay client connected")

        # Connect to Redis
        from django.conf import settings

        self.redis = redis.from_url(settings.REDIS_URL)
        self.pubsub = self.redis.pubsub()

        # Subscribe to all event channels
        await self.pubsub.subscribe("events:twitch")
        logger.info("Subscribed to Redis events:twitch channel")

        # Start Redis message listener
        self.redis_task = asyncio.create_task(self._listen_to_redis())

    async def disconnect(self, close_code):
        """Clean up Redis connections when client disconnects."""
        logger.info(f"Overlay client disconnected with code: {close_code}")

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
            logger.warning(f"Error closing Redis pubsub: {e}")

        try:
            if self.redis:
                await self.redis.close()
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")

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
                            f"Broadcasted {event_data['event_type']} event to overlay client"
                        )

                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Error processing Redis message: {e}")
                    except Exception as e:
                        logger.error(f"Error broadcasting message to WebSocket: {e}")
                        break

        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled")
        except Exception as e:
            logger.error(f"Error in Redis listener: {e}")

    async def receive(self, text_data):
        """Handle messages from WebSocket clients (if needed for control)."""
        try:
            data = json.loads(text_data)
            logger.debug(f"Received message from overlay client: {data}")

            # Handle client messages if needed (e.g., for overlay control)
            # For now, just log them

        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from overlay client: {text_data}")
