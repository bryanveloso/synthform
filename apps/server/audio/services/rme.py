"""RME TotalMix FX service for audio interface control and monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable

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

        # State tracking
        self._mic_muted = False
        self._mic_level = 0.0
        self._callbacks = []
        self._broadcast_queue = None  # Sequential FIFO queue for broadcasts
        self._queue_worker_task = None

        logger.info(
            f"[RME] Service initialized. host={self.totalmix_host} port={self.totalmix_send_port}"
        )

    async def startup(self):
        """Start the RME TotalMix service."""
        if self._running:
            return

        self._running = True

        # Initialize Redis client
        if not self._redis_client:
            redis_url = (
                settings.REDIS_URL
                if hasattr(settings, "REDIS_URL")
                else "redis://redis:6379/0"
            )
            self._redis_client = redis.Redis.from_url(redis_url)

        # Initialize broadcast queue for FIFO ordering
        if not self._broadcast_queue:
            self._broadcast_queue = asyncio.Queue()
            self._queue_worker_task = asyncio.create_task(
                self._process_broadcast_queue()
            )

        # Initialize OSC client for sending commands
        self._osc_client = SimpleUDPClient(self.totalmix_host, self.totalmix_send_port)

        # Setup OSC server for receiving updates
        await self._setup_osc_server()

        # Restore persisted state
        await self._restore_persisted_state()

        # Request initial state
        await self._request_initial_state()

        logger.info("[RME] Service started.")

    async def shutdown(self):
        """Shutdown the RME TotalMix service."""
        if not self._running:
            return

        self._running = False

        # Cancel broadcast queue worker
        if self._queue_worker_task and not self._queue_worker_task.done():
            self._queue_worker_task.cancel()
            try:
                await self._queue_worker_task
            except asyncio.CancelledError:
                pass

        # Close OSC server
        if self._osc_transport:
            self._osc_transport.close()
        if self._osc_server:
            self._osc_server.shutdown()

        # Close Redis
        if self._redis_client:
            await self._redis_client.close()

        logger.info("[RME] Service shut down.")

    async def _process_broadcast_queue(self):
        """Sequential worker that processes broadcast queue in FIFO order."""
        while True:
            try:
                broadcast_type, _ = await self._broadcast_queue.get()
                try:
                    if broadcast_type == "mic_state":
                        await self._broadcast_mic_state()
                    elif broadcast_type == "mic_level":
                        await self._broadcast_mic_level()
                    elif broadcast_type == "persist_mute":
                        await self._persist_mute_state()
                except Exception as e:
                    logger.error(
                        f'[RME] Failed to process queued broadcast. type={broadcast_type} error="{str(e)}"'
                    )
                finally:
                    self._broadcast_queue.task_done()
            except asyncio.CancelledError:
                logger.info("[RME] Broadcast queue worker stopped.")
                break
            except Exception as e:
                logger.error(f'[RME] Error in broadcast queue worker. error="{str(e)}"')

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
            logger.info(
                f"[RME] OSC server listening. port={self.totalmix_receive_port}"
            )

        except Exception as e:
            logger.error(f'[RME] Failed to setup OSC server. error="{str(e)}"')
            raise

    async def _restore_persisted_state(self):
        """Restore mic mute state from Redis."""
        try:
            if not self._redis_client:
                return

            # Get persisted mute state
            state_key = f"rme:mic:{self.mic_channel}:muted"
            saved_state = await self._redis_client.get(state_key)

            if saved_state is not None:
                self._mic_muted = saved_state == b"1" or saved_state == "1"
                state_str = "MUTED" if self._mic_muted else "UNMUTED"
                logger.info(f"[RME] Mic mute state restored. state={state_str}")
            else:
                logger.debug("[RME] No persisted mic mute state found.")

        except Exception as e:
            logger.error(f'[RME] Failed to restore persisted state. error="{str(e)}"')

    async def _persist_mute_state(self):
        """Save mic mute state to Redis for persistence across restarts."""
        try:
            if not self._redis_client:
                return

            state_key = f"rme:mic:{self.mic_channel}:muted"
            await self._redis_client.set(state_key, "1" if self._mic_muted else "0")
            state_str = "MUTED" if self._mic_muted else "UNMUTED"
            logger.debug(f"[RME] Mic mute state persisted. state={state_str}")

        except Exception as e:
            logger.warning(f'[RME] Failed to persist mute state. error="{str(e)}"')

    async def _request_initial_state(self):
        """Request initial state from TotalMix."""
        try:
            logger.info(
                f"[RME] Sending OSC commands to TotalMix. host={self.totalmix_host} port={self.totalmix_send_port}"
            )

            # Enable OSC updates from TotalMix
            self._osc_client.send_message("/1/busInput", 1)  # Enable input bus
            logger.debug("[RME] Sent OSC command. address=/1/busInput value=1")

            # Request current mute state for mic channel
            # TotalMix doesn't have a direct query, but sending a value triggers a response
            channel_addr = f"/1/mute{self.mic_channel + 1}"
            self._osc_client.send_message(channel_addr, -1)  # Query current state
            logger.debug(f"[RME] Sent OSC command. address={channel_addr} value=-1")

            logger.info(f"[RME] Requested initial state. channel={self.mic_channel}")

        except Exception as e:
            logger.error(f'[RME] Failed to request initial state. error="{str(e)}"')

    def _handle_any_osc(self, address: str, *args):
        """Catch-all handler to log ANY incoming OSC message."""
        # Only log non-heartbeat messages to reduce noise
        if address != "/":
            logger.debug(f"[RME] OSC message received. address={address} args={args}")

        # Since wildcards might not work, handle mute messages here
        if address.startswith("/1/mute/"):
            self._handle_mute_update(address, *args)
        elif address.startswith("/1/solo/"):
            self._handle_solo_update(address, *args)
        elif address.startswith("/1/volume/"):
            self._handle_volume_update(address, *args)
        elif address.startswith("/1/pan/"):
            self._handle_pan_update(address, *args)

    def _handle_mute_update(self, address: str, *args):
        """Handle mute state update from TotalMix with /1/mute/<bus>/<channel> format."""
        # Parse the address to get bus and channel
        parts = address.split("/")
        if len(parts) >= 5:  # Need 5 parts: '', '1', 'mute', bus, channel
            try:
                bus = int(parts[3]) - 1  # Convert to 0-based
                channel = int(parts[4]) - 1  # Convert to 0-based

                # Check if this is our mic channel (channel 0, bus 0)
                if channel == self.mic_channel and bus == 0:
                    # In TotalMix OSC: 0 = unmuted, 1 = muted
                    new_mute_state = bool(args[0]) if args else False

                    if new_mute_state != self._mic_muted:
                        self._mic_muted = new_mute_state
                        state_str = "MUTED" if new_mute_state else "UNMUTED"
                        logger.info(
                            f"[RME] Mic mute state changed. channel={channel} state={state_str}"
                        )

                        # Persist state for restoration on restart
                        self._broadcast_queue.put_nowait(("persist_mute", None))

                        # Broadcast state change
                        self._broadcast_queue.put_nowait(("mic_state", None))

                        # Call registered callbacks
                        for callback in self._callbacks:
                            try:
                                callback(self._mic_muted)
                            except Exception as e:
                                logger.error(
                                    f'[RME] Error in mute callback. error="{str(e)}"'
                                )
            except (ValueError, IndexError) as e:
                logger.debug(
                    f'[RME] Failed to parse mute address. address={address} error="{str(e)}"'
                )

    def _handle_solo_update(self, address: str, *args):
        """Handle solo state update from TotalMix."""
        parts = address.split("/")
        if len(parts) >= 5:
            bus = parts[3]
            channel = parts[4]
            state = args[0] if args else "unknown"
            logger.debug(
                f"[RME] Solo update. bus={bus} channel={channel} state={state}"
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
                        logger.debug(
                            f"[RME] Mic level changed. channel={channel} level={new_level:.2f}"
                        )
                        self._broadcast_queue.put_nowait(("mic_level", None))
            except (ValueError, IndexError) as e:
                logger.debug(
                    f'[RME] Failed to parse volume address. address={address} error="{str(e)}"'
                )

    def _handle_pan_update(self, address: str, *args):
        """Handle pan update from TotalMix."""
        logger.debug(f"[RME] Pan update. address={address} args={args}")

    def _handle_bus_input(self, address: str, *args):
        """Handle bus input selection."""
        logger.debug(f"[RME] Bus input. args={args}")

    def _handle_bus_output(self, address: str, *args):
        """Handle bus output selection."""
        logger.debug(f"[RME] Bus output. args={args}")

    def _handle_bus_playback(self, address: str, *args):
        """Handle bus playback selection."""
        logger.debug(f"[RME] Bus playback. args={args}")

    async def _broadcast_mic_state(self):
        """Broadcast mic mute state to Redis."""
        try:
            if not self._redis_client:
                logger.warning(
                    "[RME] Cannot broadcast mic state. reason=redis_not_initialized"
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

            state_str = "MUTED" if self._mic_muted else "UNMUTED"
            logger.debug(
                f"[RME] Mic state broadcasted. state={state_str} subscribers={num_subscribers}"
            )

        except Exception as e:
            logger.warning(f'[RME] Error broadcasting mic state. error="{str(e)}"')

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
            logger.warning(f'[RME] Error broadcasting mic level. error="{str(e)}"')

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

            # Update local state and persist
            self._mic_muted = muted
            await self._persist_mute_state()

            state_str = "MUTED" if muted else "UNMUTED"
            logger.info(
                f"[RME] Set mic mute state. channel={self.mic_channel} state={state_str}"
            )

        except Exception as e:
            logger.error(f'[RME] Error setting mic mute. error="{str(e)}"')
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
