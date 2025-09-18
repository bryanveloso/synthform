"""RME TotalMix FX service for audio interface control and monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

import redis.asyncio as redis
from django.conf import settings
from django.utils import timezone
from pythonosc import dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger(__name__)


class RMETotalMixService:
    """Service for monitoring and controlling RME TotalMix FX via OSC."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._running = False
        self._osc_client = None
        self._osc_server = None
        self._redis_client = None
        self._server_task = None

        # Configuration
        self.totalmix_host = (
            settings.RME_TOTALMIX_HOST
            if hasattr(settings, "RME_TOTALMIX_HOST")
            else "127.0.0.1"
        )
        self.totalmix_send_port = (
            settings.RME_TOTALMIX_SEND_PORT
            if hasattr(settings, "RME_TOTALMIX_SEND_PORT")
            else 9001
        )
        self.totalmix_receive_port = (
            settings.RME_TOTALMIX_RECEIVE_PORT
            if hasattr(settings, "RME_TOTALMIX_RECEIVE_PORT")
            else 9000
        )

        # Default mic channel (0-based index)
        # For UCX II: Input channels 0-7 are analog, 8-15 are ADAT, etc.
        self.mic_channel = (
            settings.RME_MIC_CHANNEL if hasattr(settings, "RME_MIC_CHANNEL") else 0
        )

        # State tracking
        self._mic_muted = False
        self._mic_level = 0.0
        self._callbacks = []

        logger.info(
            f"RME TotalMix service initialized for {self.totalmix_host}:{self.totalmix_send_port}"
        )

    async def startup(self):
        """Start the RME TotalMix service."""
        if self._running:
            return

        self._running = True
        logger.info("Starting RME TotalMix service...")

        # Initialize Redis client
        if not self._redis_client:
            redis_url = (
                settings.REDIS_URL
                if hasattr(settings, "REDIS_URL")
                else "redis://redis:6379/0"
            )
            self._redis_client = redis.Redis.from_url(redis_url)

        # Initialize OSC client for sending commands
        self._osc_client = SimpleUDPClient(self.totalmix_host, self.totalmix_send_port)

        # Setup OSC server for receiving updates
        await self._setup_osc_server()

        # Request initial state
        await self._request_initial_state()

        logger.info("RME TotalMix service started")

    async def shutdown(self):
        """Shutdown the RME TotalMix service."""
        if not self._running:
            return

        logger.info("Shutting down RME TotalMix service...")
        self._running = False

        # Cancel server task
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

        # Close OSC server
        if self._osc_server:
            self._osc_server.shutdown()

        # Close Redis
        if self._redis_client:
            await self._redis_client.close()

        logger.info("RME TotalMix service shut down")

    async def _setup_osc_server(self):
        """Setup OSC server to receive updates from TotalMix."""
        try:
            # Create dispatcher for handling incoming OSC messages
            disp = dispatcher.Dispatcher()

            # Register handlers for different OSC addresses
            # TotalMix sends updates on these addresses
            disp.map("/1/busInput", self._handle_bus_input)
            disp.map("/1/busOutput", self._handle_bus_output)
            disp.map("/1/busPlayback", self._handle_bus_playback)

            # Mute state updates (format: /1/mute<channel>)
            for i in range(48):  # UCX II has up to 48 channels
                disp.map(f"/1/mute{i + 1}", self._handle_mute_update, i)

            # Volume/fader updates (format: /1/volume<channel>)
            for i in range(48):
                disp.map(f"/1/volume{i + 1}", self._handle_volume_update, i)

            # Pan updates
            for i in range(48):
                disp.map(f"/1/pan{i + 1}", self._handle_pan_update, i)

            # Create async OSC server
            self._osc_server = AsyncIOOSCUDPServer(
                ("0.0.0.0", self.totalmix_receive_port), disp, asyncio.get_event_loop()
            )

            # Start serving
            transport, protocol = await self._osc_server.create_serve_endpoint()
            logger.info(f"OSC server listening on port {self.totalmix_receive_port}")

        except Exception as e:
            logger.error(f"Failed to setup OSC server: {e}")
            raise

    async def _request_initial_state(self):
        """Request initial state from TotalMix."""
        try:
            # Enable OSC updates from TotalMix
            self._osc_client.send_message("/1/busInput", 1)  # Enable input bus

            # Request current mute state for mic channel
            # TotalMix doesn't have a direct query, but sending a value triggers a response
            channel_addr = f"/1/mute{self.mic_channel + 1}"
            self._osc_client.send_message(channel_addr, -1)  # Query current state

            logger.info(f"Requested initial state for channel {self.mic_channel}")

        except Exception as e:
            logger.error(f"Failed to request initial state: {e}")

    def _handle_mute_update(self, address: str, channel_index: int, *args):
        """Handle mute state update from TotalMix."""
        try:
            if channel_index == self.mic_channel:
                # In TotalMix OSC: 0 = unmuted, 1 = muted
                new_mute_state = bool(args[0]) if args else False

                if new_mute_state != self._mic_muted:
                    self._mic_muted = new_mute_state
                    logger.info(
                        f"Mic channel {channel_index} mute state: {'MUTED' if new_mute_state else 'UNMUTED'}"
                    )

                    # Broadcast state change
                    asyncio.create_task(self._broadcast_mic_state())

                    # Call registered callbacks
                    for callback in self._callbacks:
                        try:
                            callback(self._mic_muted)
                        except Exception as e:
                            logger.error(f"Error in mute callback: {e}")

        except Exception as e:
            logger.error(f"Error handling mute update: {e}")

    def _handle_volume_update(self, address: str, channel_index: int, *args):
        """Handle volume update from TotalMix."""
        try:
            if channel_index == self.mic_channel:
                # Volume is 0.0 to 1.0
                new_level = float(args[0]) if args else 0.0

                if abs(new_level - self._mic_level) > 0.01:  # Threshold to avoid spam
                    self._mic_level = new_level
                    logger.debug(f"Mic channel {channel_index} level: {new_level:.2f}")

                    # Broadcast level update
                    asyncio.create_task(self._broadcast_mic_level())

        except Exception as e:
            logger.error(f"Error handling volume update: {e}")

    def _handle_pan_update(self, address: str, channel_index: int, *args):
        """Handle pan update from TotalMix."""
        # We can track pan if needed, but for now just log it
        if channel_index == self.mic_channel:
            logger.debug(
                f"Mic channel {channel_index} pan: {args[0] if args else 'unknown'}"
            )

    def _handle_bus_input(self, address: str, *args):
        """Handle bus input selection."""
        logger.debug(f"Bus input: {args}")

    def _handle_bus_output(self, address: str, *args):
        """Handle bus output selection."""
        logger.debug(f"Bus output: {args}")

    def _handle_bus_playback(self, address: str, *args):
        """Handle bus playback selection."""
        logger.debug(f"Bus playback: {args}")

    async def _broadcast_mic_state(self):
        """Broadcast mic mute state to Redis."""
        try:
            if not self._redis_client:
                return

            message = {
                "event_type": "audio.mic.mute",
                "source": "rme_totalmix",
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "muted": self._mic_muted,
                    "channel": self.mic_channel,
                    "channel_name": f"Input {self.mic_channel + 1}",
                },
            }

            # Publish to audio events channel
            await self._redis_client.publish("events:audio", json.dumps(message))

            logger.debug(
                f"Broadcasted mic mute state: {'MUTED' if self._mic_muted else 'UNMUTED'}"
            )

        except Exception as e:
            logger.error(f"Error broadcasting mic state: {e}")

    async def _broadcast_mic_level(self):
        """Broadcast mic level to Redis."""
        try:
            if not self._redis_client:
                return

            message = {
                "event_type": "audio.mic.level",
                "source": "rme_totalmix",
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "level": self._mic_level,
                    "channel": self.mic_channel,
                    "channel_name": f"Input {self.mic_channel + 1}",
                },
            }

            # Publish to audio events channel
            await self._redis_client.publish("events:audio", json.dumps(message))

        except Exception as e:
            logger.error(f"Error broadcasting mic level: {e}")

    # Public API methods

    def is_mic_muted(self) -> bool:
        """Get current mic mute state."""
        return self._mic_muted

    def get_mic_level(self) -> float:
        """Get current mic level (0.0 to 1.0)."""
        return self._mic_level

    async def set_mic_mute(self, muted: bool):
        """Set mic mute state."""
        try:
            if not self._osc_client:
                raise RuntimeError("OSC client not initialized")

            channel_addr = f"/1/mute{self.mic_channel + 1}"
            value = 1 if muted else 0
            self._osc_client.send_message(channel_addr, value)

            logger.info(
                f"Set mic channel {self.mic_channel} to {'MUTED' if muted else 'UNMUTED'}"
            )

        except Exception as e:
            logger.error(f"Error setting mic mute: {e}")
            raise

    async def toggle_mic_mute(self):
        """Toggle mic mute state."""
        await self.set_mic_mute(not self._mic_muted)

    def register_mute_callback(self, callback: Callable[[bool], None]):
        """Register a callback for mute state changes."""
        self._callbacks.append(callback)

    def unregister_mute_callback(self, callback: Callable[[bool], None]):
        """Unregister a mute state callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def get_current_state(self) -> dict:
        """Get current audio interface state."""
        return {
            "connected": self._running,
            "mic_muted": self._mic_muted,
            "mic_level": self._mic_level,
            "mic_channel": self.mic_channel,
            "mic_channel_name": f"Input {self.mic_channel + 1}",
        }


# Service instance
rme_service = RMETotalMixService()
