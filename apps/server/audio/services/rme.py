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
        self._osc_transport = None
        self._redis_client = None

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

        # Channels to monitor for multi-channel setup
        self.monitored_channels = (
            settings.RME_MONITORED_CHANNELS
            if hasattr(settings, "RME_MONITORED_CHANNELS")
            else [
                0,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
            ]  # Default: Mic 1 + all ADAT for testing
        )

        # State tracking - now for multiple channels
        self._channel_states = {
            channel: {
                "muted": False,
                "level": 0.0,
                "label": self._get_channel_label(channel),
            }
            for channel in self.monitored_channels
        }

        # Keep old single-channel state for backwards compatibility
        self._mic_muted = False
        self._mic_level = 0.0
        self._callbacks = []

        logger.info(
            f"RME TotalMix service initialized for {self.totalmix_host}:{self.totalmix_send_port}"
        )
        logger.info(f"Monitoring channels: {self.monitored_channels}")

    def _get_channel_label(self, channel: int) -> str:
        """Get a human-readable label for a channel."""
        if channel < 8:
            return f"Analog {channel + 1}"
        elif channel < 16:
            return f"ADAT {channel - 7}"
        else:
            return f"Input {channel + 1}"

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

        # Close OSC server
        if self._osc_transport:
            self._osc_transport.close()
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

            # Add a catch-all handler to log ANY incoming OSC message
            disp.set_default_handler(self._handle_any_osc)

            # Don't register specific handlers - let the catch-all handle everything
            # This ensures we see ALL messages

            # Create async OSC server
            self._osc_server = AsyncIOOSCUDPServer(
                ("0.0.0.0", self.totalmix_receive_port), disp, asyncio.get_event_loop()
            )

            # Start serving and keep reference to transport
            self._osc_transport, _ = await self._osc_server.create_serve_endpoint()
            logger.info(f"OSC server listening on port {self.totalmix_receive_port}")

        except Exception as e:
            logger.error(f"Failed to setup OSC server: {e}")
            raise

    async def _request_initial_state(self):
        """Request initial state from TotalMix."""
        try:
            logger.info(
                f"Sending OSC commands to TotalMix at {self.totalmix_host}:{self.totalmix_send_port}"
            )

            # Enable OSC updates from TotalMix
            self._osc_client.send_message("/1/busInput", 1)  # Enable input bus
            logger.debug("Sent /1/busInput = 1")

            # Try to enable playback bus monitoring
            self._osc_client.send_message("/1/busPlayback", 1.0)  # Switch to playback bus
            logger.debug("Sent /1/busPlayback = 1.0")

            # Send a query to trigger playback channel responses
            for i in range(16):  # Query first 16 playback channels
                self._osc_client.send_message(f"/1/mute{i+1}", -1)
                logger.debug(f"Querying playback channel {i+1}")

            # Switch back to input bus
            self._osc_client.send_message("/1/busInput", 1.0)
            logger.debug("Sent /1/busInput = 1.0")

            self._osc_client.send_message("/1/busOutput", 1)  # Enable output bus
            logger.debug("Sent /1/busOutput = 1")

            # Request current mute state for mic channel
            # TotalMix doesn't have a direct query, but sending a value triggers a response
            channel_addr = f"/1/mute{self.mic_channel + 1}"
            self._osc_client.send_message(channel_addr, -1)  # Query current state
            logger.debug(f"Sent {channel_addr} = -1")

            logger.info(f"Requested initial state for channel {self.mic_channel}")

        except Exception as e:
            logger.error(f"Failed to request initial state: {e}")

    def _handle_any_osc(self, address: str, *args):
        """Catch-all handler to log ANY incoming OSC message."""
        # Log EVERYTHING except heartbeats to see what we get from playback channels
        if address != "/":
            # Always log to see ALL traffic when debugging
            logger.info(f"🔵 OSC IN: address={address}, args={args}")

        # Handle mute messages from ANY page (1, 2, 3, etc.)
        if "/mute" in address:
            logger.info(f"🎯 MUTE MESSAGE: address={address}, args={args}")
            self._handle_mute_update(address, *args)
        elif address.startswith("/1/solo/"):
            self._handle_solo_update(address, *args)
        elif address.startswith("/1/volume/"):
            self._handle_volume_update(address, *args)
        elif address.startswith("/1/pan/"):
            self._handle_pan_update(address, *args)

    def _handle_mute_update(self, address: str, *args):
        """Handle mute state update from TotalMix.

        Formats seen:
        - /1/mute/<row>/<channel> - Page 1 format (row: 1=Input, 2=Playback, 3=Output)
        - /2/mute/<channel> - Page 2 format (for direct channel access)
        - /3/mute/<channel> - Page 3 format (for mute groups)
        """
        # Parse the address
        parts = address.split("/")

        # Log the raw format to understand what we're getting
        logger.info(f"📝 MUTE RAW: parts={parts}, args={args}")

        if len(parts) >= 5 and parts[2] == "mute":  # Format: /page/mute/row/channel
            try:
                page = int(parts[1]) if parts[1].isdigit() else 1
                row = int(parts[3])  # 1=Input, 2=Playback, 3=Output
                channel = int(parts[4]) - 1  # Convert to 0-based

                # In TotalMix OSC: 0 = unmuted, 1 = muted
                new_mute_state = bool(args[0]) if args else False

                # Log ALL activity from both input and playback rows
                if row == 1:  # Hardware Input row
                    channel_label = (
                        self._get_channel_label(channel)
                        if hasattr(self, "_get_channel_label")
                        else f"Input {channel + 1}"
                    )
                    logger.info(
                        f"🎚️ INPUT CHANNEL {channel} ({channel_label}) mute state: {'MUTED' if new_mute_state else 'UNMUTED'}"
                    )
                elif row == 2:  # Software Playback row
                    # This is where Discord would show up!
                    logger.info(
                        f"🎧 PLAYBACK CHANNEL {channel} (Software {channel + 1}) mute state: {'MUTED' if new_mute_state else 'UNMUTED'}"
                    )

                # Update state if monitored (only for hardware inputs for now)
                if row == 1 and channel in self.monitored_channels:
                    if new_mute_state != self._channel_states[channel]["muted"]:
                        self._channel_states[channel]["muted"] = new_mute_state

                        # Update backwards-compatible mic state if this is the mic channel
                        if channel == self.mic_channel:
                            self._mic_muted = new_mute_state
                            asyncio.create_task(self._broadcast_mic_state())
                            # Call registered callbacks
                            for callback in self._callbacks:
                                try:
                                    callback(self._mic_muted)
                                except Exception as e:
                                    logger.error(f"Error in mute callback: {e}")

                        # Broadcast all channel states
                        asyncio.create_task(self._broadcast_channel_states())

            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse mute address {address}: {e}")

    def _handle_solo_update(self, address: str, *args):
        """Handle solo state update from TotalMix."""
        parts = address.split("/")
        if len(parts) >= 5:
            bus = parts[3]
            channel = parts[4]
            logger.debug(
                f"Solo update: bus={bus}, channel={channel}, state={args[0] if args else 'unknown'}"
            )

    def _handle_volume_update(self, address: str, *args):
        """Handle volume update from TotalMix with /1/volume/<bus>/<channel> format."""
        parts = address.split("/")
        if len(parts) >= 5:
            try:
                bus = int(parts[3]) - 1
                channel = int(parts[4]) - 1

                if channel == self.mic_channel and bus == 0:
                    new_level = float(args[0]) if args else 0.0
                    if abs(new_level - self._mic_level) > 0.01:
                        self._mic_level = new_level
                        logger.debug(f"Mic channel {channel} level: {new_level:.2f}")
                        asyncio.create_task(self._broadcast_mic_level())
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse volume address {address}: {e}")

    def _handle_pan_update(self, address: str, *args):
        """Handle pan update from TotalMix."""
        logger.debug(f"Pan update: address={address}, args={args}")

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
                logger.warning(
                    "Redis client not initialized, cannot broadcast mic state"
                )
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
            num_subscribers = await self._redis_client.publish(
                "events:audio", json.dumps(message)
            )

            logger.debug(
                f"Broadcasted mic mute state: {'MUTED' if self._mic_muted else 'UNMUTED'} to {num_subscribers} subscribers"
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

    async def _broadcast_channel_states(self):
        """Broadcast all channel states to Redis."""
        try:
            if not self._redis_client:
                logger.warning(
                    "Redis client not initialized, cannot broadcast channel states"
                )
                return

            message = {
                "event_type": "audio.channels.update",
                "source": "rme_totalmix",
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "channels": [
                        {
                            "channel": ch,
                            "label": state["label"],
                            "muted": state["muted"],
                            "level": state["level"],
                        }
                        for ch, state in self._channel_states.items()
                    ]
                },
            }

            # Publish to audio events channel
            num_subscribers = await self._redis_client.publish(
                "events:audio", json.dumps(message)
            )

            logger.debug(
                f"Broadcasted {len(self._channel_states)} channel states to {num_subscribers} subscribers"
            )

        except Exception as e:
            logger.error(f"Error broadcasting channel states: {e}")

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

    async def get_channel_states(self) -> dict:
        """Get all monitored channel states."""
        return {
            "connected": self._running,
            "channels": [
                {
                    "channel": ch,
                    "label": state["label"],
                    "muted": state["muted"],
                    "level": state["level"],
                }
                for ch, state in self._channel_states.items()
            ],
        }


# Service instance
rme_service = RMETotalMixService()
