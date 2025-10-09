from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as redis
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)


class AdConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for ad warning notifications."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = None
        self.pubsub = None
        self.redis_task = None

    async def connect(self):
        """Accept WebSocket connection and start Redis subscription."""
        await self.accept()
        logger.info("[Ads] Consumer connected.")

        # Connect to Redis
        self.redis = redis.from_url(settings.REDIS_URL)
        self.pubsub = self.redis.pubsub()

        # Subscribe to ad events channel
        await self.pubsub.subscribe("events:ads")
        logger.info("[Ads] Subscribed to Redis channel. channel=events:ads")

        # Start Redis message listener
        self.redis_task = asyncio.create_task(self._listen_to_redis())

    async def disconnect(self, close_code):
        """Clean up Redis connections when client disconnects."""
        logger.info(f"[Ads] Consumer disconnected. code={close_code}")

        # Cancel Redis listener task
        if self.redis_task:
            self.redis_task.cancel()
            try:
                await self.redis_task
            except asyncio.CancelledError:
                pass

        # Close Redis connections
        try:
            if self.pubsub:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()
        except Exception as e:
            logger.warning(f'[Ads] Error closing Redis pubsub. error="{str(e)}"')

        try:
            if self.redis:
                await self.redis.close()
        except Exception as e:
            logger.warning(f'[Ads] Error closing Redis connection. error="{str(e)}"')

    async def _listen_to_redis(self):
        """Listen for Redis pub/sub messages and broadcast to WebSocket."""
        try:
            while True:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    try:
                        # Parse the Redis message
                        ad_data = json.loads(message["data"])

                        # Send to WebSocket client (overlay)
                        await self.send(text_data=json.dumps(ad_data))

                        logger.debug(
                            f"[Ads] Broadcasted to consumer. type={ad_data.get('type')}"
                        )

                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(
                            f'[Ads] Error processing Redis message. error="{str(e)}"'
                        )
                    except Exception as e:
                        logger.error(
                            f'[Ads] Error broadcasting message to WebSocket. error="{str(e)}"'
                        )
                        # Continue listening even if broadcast fails

        except asyncio.CancelledError:
            logger.info("[Ads] Redis listener task cancelled.")
        except Exception as e:
            logger.error(f'[Ads] Error in Redis listener. error="{str(e)}"')

    async def receive(self, text_data):
        """Handle messages from WebSocket clients."""
        try:
            data = json.loads(text_data)
            command = data.get("command")

            if command == "status":
                # Send current ad schedule status
                await self.send_status()
            else:
                logger.debug(f"[Ads] Received command from consumer. command={command}")

        except json.JSONDecodeError:
            logger.warning(
                f'[Ads] Received invalid JSON from consumer. data="{text_data}"'
            )

    async def send_status(self):
        """Send current ad schedule status from Redis."""
        try:
            # Reuse existing Redis connection
            enabled = await self.redis.get("ads:enabled")
            next_time = await self.redis.get("ads:next_time")
            warning_active = await self.redis.get("ads:warning_active")

            status = {
                "type": "ads:status",
                "payload": {
                    "enabled": enabled == b"true" if enabled else False,
                    "next_time": next_time.decode() if next_time else None,
                    "warning_active": warning_active == b"true"
                    if warning_active
                    else False,
                },
            }

            await self.send(text_data=json.dumps(status))

        except Exception as e:
            logger.error(f'[Ads] Error sending status. error="{str(e)}"')
