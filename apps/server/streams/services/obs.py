from __future__ import annotations

import asyncio
import json
import logging

import obsws_python as obs
import redis.asyncio as redis
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Suppress obsws_python connection errors from going to Sentry
# These are expected when OBS is not running
obs_logger = logging.getLogger("obsws_python.baseclient")
obs_logger.setLevel(logging.CRITICAL)  # Only log critical errors to Sentry


class OBSService:
    """OBS-WebSocket service for controlling OBS and broadcasting state."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client_req = None
            cls._instance._client_event = None
            cls._instance._redis_client = None
            cls._instance._running = False
            cls._instance._reconnect_task = None
            cls._instance._reconnect_delay = 1.0  # Start with 1 second delay
            cls._instance._event_tasks = set()  # Track event broadcast tasks
        return cls._instance

    def _create_event_task(self, coro):
        """Create and track event broadcast tasks."""
        task = asyncio.create_task(coro)
        self._event_tasks.add(task)
        task.add_done_callback(self._event_tasks.discard)
        return task

    def _serialize_event_data(self, event_obj: object) -> dict:
        """Safely serialize obsws-python event objects to avoid coupling to internals."""
        if not hasattr(event_obj, "attrs"):
            return event_obj if isinstance(event_obj, dict) else {}
        return {attr: getattr(event_obj, attr, None) for attr in event_obj.attrs()}

    async def startup(self):
        """Start the OBS service when ASGI application is ready."""
        if not self._running:
            logger.info("Starting OBS service...")
            await self._ensure_running()

    async def _ensure_running(self):
        """Ensure the service is running."""
        if self._running:
            return

        self._running = True

        # Initialize Redis client
        if not self._redis_client:
            self._redis_client = redis.Redis.from_url(
                settings.REDIS_URL or "redis://redis:6379/0"
            )

        logger.info("Auto-starting OBS service...")
        await self._connect()

    async def _connect(self):
        """Connect to OBS WebSocket."""
        try:
            logger.info(f"Connecting to OBS at {settings.OBS_HOST}:{settings.OBS_PORT}")

            # Initialize request client
            self._client_req = obs.ReqClient(
                host=settings.OBS_HOST,
                port=settings.OBS_PORT,
                password=settings.OBS_PASSWORD,
                timeout=5,
            )

            # Initialize event client
            self._client_event = obs.EventClient(
                host=settings.OBS_HOST,
                port=settings.OBS_PORT,
                password=settings.OBS_PASSWORD,
            )

            # Register event callbacks
            self._register_callbacks()

            # Test connection
            version = self._client_req.get_version()
            logger.info(f"Connected to OBS Studio {version.obs_version}")

            # Reset reconnect delay on successful connection
            self._reconnect_delay = 1.0

            # Broadcast initial state
            await self._broadcast_current_state()

            # Auto-refresh browser sources on connection
            if settings.OBS_AUTO_REFRESH_BROWSER_SOURCES:
                logger.info("Auto-refreshing browser sources on connection...")
                try:
                    await self.refresh_all_browser_sources()
                except Exception as e:
                    logger.warning(f"Failed to auto-refresh browser sources: {e}")

        except (TimeoutError, ConnectionRefusedError):
            # These are expected when OBS is not running - log at INFO level
            logger.info(
                f"OBS not available at {settings.OBS_HOST}:{settings.OBS_PORT} - will retry"
            )
            await self._schedule_reconnect()
        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}")
            await self._schedule_reconnect()

    async def shutdown(self):
        """Graceful shutdown of the OBS service."""
        if not self._running:
            return

        logger.info("Shutting down OBS service...")
        self._running = False

        # Cancel reconnection task if it exists
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        await self._disconnect()

    async def _disconnect(self):
        """Disconnect from OBS WebSocket."""
        try:
            if self._client_event:
                # Deregister callbacks
                for callback_name in self._client_event.callback.get():
                    self._client_event.callback.deregister(callback_name)

            # Cancel any pending event tasks
            for task in list(self._event_tasks):
                if not task.done():
                    task.cancel()
            self._event_tasks.clear()

            # Close connections (obsws-python handles this automatically)
            self._client_req = None
            self._client_event = None

            logger.info("Disconnected from OBS")
        except Exception as e:
            logger.error(f"Error disconnecting from OBS: {e}")

    async def _schedule_reconnect(self):
        """Schedule a reconnection attempt."""
        if not self._running:
            return

        logger.info(f"Scheduling reconnect in {self._reconnect_delay:.1f} seconds")
        await asyncio.sleep(self._reconnect_delay)

        # Exponential backoff, max 30 seconds
        self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

        if self._running:
            await self._connect()

    async def _validate_connection(self) -> bool:
        """Validate the OBS connection is still alive."""
        if not self._client_req:
            return False

        try:
            # Try a simple request to check connection
            self._client_req.get_version()
            return True
        except Exception as e:
            logger.debug(f"OBS connection validation failed: {e}")
            self._client_req = None
            self._client_event = None
            await self._schedule_reconnect()
            return False

    def _register_callbacks(self):
        """Register event callbacks."""
        # Scene events
        self._client_event.callback.register(self._on_current_program_scene_changed)
        self._client_event.callback.register(self._on_scene_created)
        self._client_event.callback.register(self._on_scene_removed)

        # Recording events
        self._client_event.callback.register(self._on_record_state_changed)

        # Streaming events
        self._client_event.callback.register(self._on_stream_state_changed)

        # Source events
        self._client_event.callback.register(self._on_scene_item_created)
        self._client_event.callback.register(self._on_scene_item_removed)
        self._client_event.callback.register(self._on_scene_item_enable_state_changed)

        # Input events
        self._client_event.callback.register(self._on_input_created)
        self._client_event.callback.register(self._on_input_removed)
        self._client_event.callback.register(self._on_input_name_changed)
        self._client_event.callback.register(self._on_input_mute_state_changed)

    # Event handlers
    def _on_current_program_scene_changed(self, data):
        """Handle scene change events."""
        self._create_event_task(
            self._broadcast_event("obs.scene.changed", self._serialize_event_data(data))
        )

    def _on_scene_created(self, data):
        """Handle scene creation events."""
        self._create_event_task(
            self._broadcast_event("obs.scene.created", self._serialize_event_data(data))
        )

    def _on_scene_removed(self, data):
        """Handle scene removal events."""
        self._create_event_task(
            self._broadcast_event("obs.scene.removed", self._serialize_event_data(data))
        )

    def _on_record_state_changed(self, data):
        """Handle recording state change events."""
        self._create_event_task(
            self._broadcast_event(
                "obs.recording.changed", self._serialize_event_data(data)
            )
        )

    def _on_stream_state_changed(self, data):
        """Handle streaming state change events."""
        self._create_event_task(
            self._broadcast_event(
                "obs.streaming.changed", self._serialize_event_data(data)
            )
        )

    def _on_scene_item_created(self, data):
        """Handle scene item creation events."""
        self._create_event_task(
            self._broadcast_event(
                "obs.source.created", self._serialize_event_data(data)
            )
        )

    def _on_scene_item_removed(self, data):
        """Handle scene item removal events."""
        self._create_event_task(
            self._broadcast_event(
                "obs.source.removed", self._serialize_event_data(data)
            )
        )

    def _on_scene_item_enable_state_changed(self, data):
        """Handle scene item visibility change events."""
        self._create_event_task(
            self._broadcast_event(
                "obs.source.visibility", self._serialize_event_data(data)
            )
        )

    def _on_input_created(self, data):
        """Handle input creation events."""
        self._create_event_task(
            self._broadcast_event("obs.input.created", self._serialize_event_data(data))
        )

    def _on_input_removed(self, data):
        """Handle input removal events."""
        self._create_event_task(
            self._broadcast_event("obs.input.removed", self._serialize_event_data(data))
        )

    def _on_input_name_changed(self, data):
        """Handle input name change events."""
        self._create_event_task(
            self._broadcast_event("obs.input.renamed", self._serialize_event_data(data))
        )

    def _on_input_mute_state_changed(self, data):
        """Handle input mute state change events."""
        self._create_event_task(
            self._broadcast_event("obs.input.muted", self._serialize_event_data(data))
        )

    async def _broadcast_event(self, event_type: str, data: dict):
        """Broadcast OBS event to Redis."""
        try:
            redis_message = {
                "event_type": event_type,
                "source": "obs",
                "timestamp": timezone.now().isoformat(),
                "data": data,
            }

            # Publish to OBS events channel
            channel = "events:obs"
            message_json = json.dumps(redis_message, default=str)

            await self._redis_client.publish(channel, message_json)
            logger.debug(f"Broadcasted {event_type} event to Redis channel: {channel}")

        except Exception as e:
            logger.error(f"Error broadcasting event to Redis: {e}")

    async def _broadcast_current_state(self):
        """Broadcast current OBS state on connection."""
        try:
            if not self._client_req:
                return

            # Get current scene
            current_scene = self._client_req.get_current_program_scene()
            await self._broadcast_event(
                "obs.state.current", self._serialize_event_data(current_scene)
            )

            # Get recording status
            recording_status = self._client_req.get_record_status()
            await self._broadcast_event(
                "obs.recording.status", self._serialize_event_data(recording_status)
            )

            # Get streaming status
            streaming_status = self._client_req.get_stream_status()
            await self._broadcast_event(
                "obs.streaming.status", self._serialize_event_data(streaming_status)
            )

        except (BrokenPipeError, ConnectionError, OSError) as e:
            logger.warning(f"Lost connection to OBS during state broadcast: {e}")
            self._client_req = None
            self._client_event = None
            await self._schedule_reconnect()
        except Exception as e:
            logger.error(f"Error broadcasting current state: {e}")

    # Public access methods
    def is_connected(self) -> bool:
        """Check if OBS service is connected."""
        return self._client_req is not None

    async def get_current_state(self) -> dict | None:
        """Get current OBS state for overlay consumption."""
        await self._ensure_running()

        try:
            if not self._client_req:
                return {"message": "OBS not connected", "connected": False}

            # Get current scene
            current_scene = self._client_req.get_current_program_scene()

            # Get recording status
            recording_status = self._client_req.get_record_status()

            # Get streaming status
            streaming_status = self._client_req.get_stream_status()

            return {
                "current_scene": self._serialize_event_data(current_scene),
                "recording": self._serialize_event_data(recording_status),
                "streaming": self._serialize_event_data(streaming_status),
                "connected": True,
            }

        except (BrokenPipeError, ConnectionError, OSError) as e:
            logger.info(f"OBS disconnected: {e}. Will reconnect when available.")
            self._client_req = None
            self._client_event = None
            await self._schedule_reconnect()
            return {"message": "OBS reconnecting", "connected": False}
        except json.JSONDecodeError as e:
            # This happens when OBS returns invalid/empty JSON
            logger.debug(f"OBS returned invalid JSON: {e}")
            return {"message": "OBS not connected", "connected": False}
        except Exception as e:
            # Check if it's a connection-related error
            error_msg = str(e).lower()
            if (
                "broken pipe" in error_msg
                or "connection" in error_msg
                or "errno 32" in error_msg
            ):
                logger.info(f"OBS disconnected: {e}. Will reconnect when available.")
                self._client_req = None
                self._client_event = None
                await self._schedule_reconnect()
                return {"message": "OBS reconnecting", "connected": False}

            logger.error(f"Unexpected error getting OBS state: {e}")
            return {"message": "OBS state unavailable", "connected": False}

    # Control methods
    async def switch_scene(self, scene_name: str):
        """Switch to a specific scene."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.set_current_program_scene(scene_name)
            logger.info(f"Switched to scene: {scene_name}")

        except Exception as e:
            logger.error(f"Error switching to scene {scene_name}: {e}")
            raise

    async def start_recording(self):
        """Start recording."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.start_record()
            logger.info("Started recording")

        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            raise

    async def stop_recording(self):
        """Stop recording."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.stop_record()
            logger.info("Stopped recording")

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            raise

    async def start_streaming(self):
        """Start streaming."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.start_stream()
            logger.info("Started streaming")

        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            raise

    async def stop_streaming(self):
        """Stop streaming."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.stop_stream()
            logger.info("Stopped streaming")

        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            raise

    async def toggle_source(self, scene_name: str, source_name: str):
        """Toggle source visibility in a specific scene."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            # Get current source state
            current_state = self._client_req.get_scene_item_enabled(
                scene_name, source_name
            )

            # Toggle it
            new_state = not current_state.scene_item_enabled
            self._client_req.set_scene_item_enabled(scene_name, source_name, new_state)

            logger.info(
                f"Toggled source {source_name} in scene {scene_name}: {new_state}"
            )

        except Exception as e:
            logger.error(f"Error toggling source {source_name}: {e}")
            raise

    async def get_scenes(self) -> list[str]:
        """Get list of available scenes."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            scenes = self._client_req.get_scene_list()
            return [scene["sceneName"] for scene in scenes.scenes]

        except Exception as e:
            logger.error(f"Error getting scenes: {e}")
            raise

    async def get_sources(self, scene_name: str) -> list[dict]:
        """Get list of sources in a specific scene."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            scene_items = self._client_req.get_scene_item_list(scene_name)
            return [
                {
                    "name": item["sourceName"],
                    "enabled": item["sceneItemEnabled"],
                    "id": item["sceneItemId"],
                }
                for item in scene_items.scene_items
            ]

        except Exception as e:
            logger.error(f"Error getting sources for scene {scene_name}: {e}")
            raise

    async def get_browser_sources(self) -> list[dict]:
        """Get all browser sources across all scenes."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            browser_sources = []

            # Get list of all inputs/sources
            inputs = self._client_req.get_input_list()

            for input_item in inputs.inputs:
                # Check if this is a browser source
                if input_item["inputKind"] == "browser_source":
                    # Get the settings to find the URL
                    settings = self._client_req.get_input_settings(
                        input_item["inputName"]
                    )
                    browser_sources.append(
                        {
                            "name": input_item["inputName"],
                            "kind": input_item["inputKind"],
                            "url": settings.input_settings.get("url", ""),
                            "width": settings.input_settings.get("width", 1920),
                            "height": settings.input_settings.get("height", 1080),
                        }
                    )

            logger.info(f"Found {len(browser_sources)} browser sources")
            return browser_sources

        except Exception as e:
            logger.error(f"Error getting browser sources: {e}")
            raise

    async def refresh_browser_source(self, source_name: str):
        """Refresh a specific browser source."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            # Method 1: Press the refresh button (if available in OBS WebSocket v5)
            try:
                self._client_req.press_input_properties_button(
                    source_name, "refreshnocache"
                )
                logger.info(f"Refreshed browser source: {source_name}")
                return
            except Exception:
                # If button press doesn't work, try method 2
                pass

            # Method 2: Toggle URL to force reload
            settings = self._client_req.get_input_settings(source_name)
            current_url = settings.input_settings.get("url", "")

            if current_url:
                # Temporarily set to blank then back to force reload
                self._client_req.set_input_settings(
                    source_name, {"url": "about:blank"}, overlay=True
                )
                # Small delay
                await asyncio.sleep(0.1)
                # Restore original URL
                self._client_req.set_input_settings(
                    source_name, {"url": current_url}, overlay=True
                )
                logger.info(f"Force-refreshed browser source: {source_name}")
            else:
                logger.warning(f"Browser source {source_name} has no URL configured")

        except Exception as e:
            logger.error(f"Error refreshing browser source {source_name}: {e}")
            raise

    async def refresh_all_browser_sources(self):
        """Refresh all browser sources in OBS."""
        try:
            browser_sources = await self.get_browser_sources()

            for source in browser_sources:
                try:
                    await self.refresh_browser_source(source["name"])
                    # Small delay between refreshes to avoid overload
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Failed to refresh {source['name']}: {e}")
                    continue

            logger.info(f"Refreshed {len(browser_sources)} browser sources")

            # Broadcast refresh event
            await self._broadcast_event(
                "obs.browser_sources.refreshed",
                {"count": len(browser_sources), "sources": browser_sources},
            )

        except Exception as e:
            logger.error(f"Error refreshing all browser sources: {e}")
            raise


# Service instance - automatically starts when imported
obs_service = OBSService()
