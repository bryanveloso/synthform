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
            cls._instance._event_queue = None  # Sequential FIFO queue for broadcasts
            cls._instance._queue_worker_task = None
        return cls._instance

    def _serialize_event_data(self, event_obj: object) -> dict:
        """Safely serialize obsws-python event objects to avoid coupling to internals."""
        if not hasattr(event_obj, "attrs"):
            return event_obj if isinstance(event_obj, dict) else {}
        return {attr: getattr(event_obj, attr, None) for attr in event_obj.attrs()}

    async def _process_event_queue(self):
        """Sequential worker that processes event queue in FIFO order."""
        while True:
            try:
                event_type, data = await self._event_queue.get()
                try:
                    await self._broadcast_event(event_type, data)
                except Exception as e:
                    logger.error(
                        f'[OBS] Failed to broadcast queued event. event_type={event_type} error="{str(e)}"'
                    )
                finally:
                    self._event_queue.task_done()
            except asyncio.CancelledError:
                logger.info("[OBS] Event queue worker stopped.")
                break
            except Exception as e:
                logger.error(f'[OBS] Error in event queue worker. error="{str(e)}"')

    async def startup(self):
        """Start the OBS service when ASGI application is ready."""
        if not self._running:
            logger.info("[OBS] Service starting.")
            await self._ensure_running()

    async def _ensure_running(self):
        """Ensure the service is running."""
        if self._running:
            return

        self._running = True

        # Initialize Redis client
        if not self._redis_client:
            self._redis_client = redis.from_url(
                settings.REDIS_URL or "redis://redis:6379/0"
            )

        # Initialize event queue for FIFO ordering
        if not self._event_queue:
            self._event_queue = asyncio.Queue()
            self._queue_worker_task = asyncio.create_task(self._process_event_queue())

        logger.info("[OBS] Service auto-starting.")
        await self._connect()

    async def _connect(self):
        """Connect to OBS WebSocket."""
        try:
            logger.info(
                f"[OBS] Connecting. host={settings.OBS_HOST} port={settings.OBS_PORT}"
            )

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
            logger.info(f"[OBS] Connected to OBS Studio. version={version.obs_version}")

            # Reset reconnect delay on successful connection
            self._reconnect_delay = 1.0

            # Broadcast initial state
            await self._broadcast_current_state()

            # Auto-refresh browser sources on connection
            if settings.OBS_AUTO_REFRESH_BROWSER_SOURCES:
                logger.info("[OBS] Auto-refreshing browser sources on connection.")
                try:
                    await self.refresh_all_browser_sources()
                except Exception as e:
                    logger.warning(
                        f'[OBS] Failed to auto-refresh browser sources. error="{str(e)}"'
                    )

        except (TimeoutError, ConnectionRefusedError):
            # These are expected when OBS is not running - log at INFO level
            logger.info(
                f"[OBS] Not available, will retry. host={settings.OBS_HOST} port={settings.OBS_PORT}"
            )
            await self._schedule_reconnect()
        except Exception as e:
            logger.error(f'[OBS] ❌ Failed to connect. error="{str(e)}"')
            await self._schedule_reconnect()

    async def shutdown(self):
        """Graceful shutdown of the OBS service."""
        if not self._running:
            return

        logger.info("[OBS] Service shutting down.")
        self._running = False

        # Cancel reconnection task if it exists
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        # Cancel event queue worker
        if self._queue_worker_task and not self._queue_worker_task.done():
            self._queue_worker_task.cancel()
            try:
                await self._queue_worker_task
            except asyncio.CancelledError:
                pass

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

            logger.info("[OBS] Disconnected.")
        except Exception as e:
            logger.error(f'[OBS] ❌ Error disconnecting. error="{str(e)}"')

    async def _schedule_reconnect(self):
        """Schedule a reconnection attempt."""
        if not self._running:
            return

        logger.info(f"[OBS] Scheduling reconnect. delay={self._reconnect_delay:.1f}s")
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
            logger.debug(f'[OBS] Connection validation failed. error="{str(e)}"')
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
        self._event_queue.put_nowait(
            ("obs:scene:changed", self._serialize_event_data(data))
        )

    def _on_scene_created(self, data):
        """Handle scene creation events."""
        self._event_queue.put_nowait(
            ("obs:scene:created", self._serialize_event_data(data))
        )

    def _on_scene_removed(self, data):
        """Handle scene removal events."""
        self._event_queue.put_nowait(
            ("obs:scene:removed", self._serialize_event_data(data))
        )

    def _on_record_state_changed(self, data):
        """Handle recording state change events."""
        self._event_queue.put_nowait(
            ("obs:recording:changed", self._serialize_event_data(data))
        )

    def _on_stream_state_changed(self, data):
        """Handle streaming state change events."""
        self._event_queue.put_nowait(
            ("obs:streaming:changed", self._serialize_event_data(data))
        )

    def _on_scene_item_created(self, data):
        """Handle scene item creation events."""
        self._event_queue.put_nowait(
            ("obs:source:created", self._serialize_event_data(data))
        )

    def _on_scene_item_removed(self, data):
        """Handle scene item removal events."""
        self._event_queue.put_nowait(
            ("obs:source:removed", self._serialize_event_data(data))
        )

    def _on_scene_item_enable_state_changed(self, data):
        """Handle scene item visibility change events."""
        self._event_queue.put_nowait(
            ("obs:source:visibility", self._serialize_event_data(data))
        )

    def _on_input_created(self, data):
        """Handle input creation events."""
        self._event_queue.put_nowait(
            ("obs:input:created", self._serialize_event_data(data))
        )

    def _on_input_removed(self, data):
        """Handle input removal events."""
        self._event_queue.put_nowait(
            ("obs:input:removed", self._serialize_event_data(data))
        )

    def _on_input_name_changed(self, data):
        """Handle input name change events."""
        self._event_queue.put_nowait(
            ("obs:input:renamed", self._serialize_event_data(data))
        )

    def _on_input_mute_state_changed(self, data):
        """Handle input mute state change events."""
        self._event_queue.put_nowait(
            ("obs:input:muted", self._serialize_event_data(data))
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
            logger.debug(
                f"[OBS] Broadcasted event to Redis. event_type={event_type} channel={channel}"
            )

        except Exception as e:
            logger.error(
                f'[OBS] ❌ Failed to broadcast event to Redis. error="{str(e)}"'
            )

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
            logger.warning(
                f'[OBS] 🟡 Lost connection during state broadcast. error="{str(e)}"'
            )
            self._client_req = None
            self._client_event = None
            await self._schedule_reconnect()
        except Exception as e:
            logger.error(
                f'[OBS] ❌ Failed to broadcast current state. error="{str(e)}"'
            )

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
            logger.info(f'[OBS] Disconnected, will reconnect. error="{str(e)}"')
            self._client_req = None
            self._client_event = None
            await self._schedule_reconnect()
            return {"message": "OBS reconnecting", "connected": False}
        except json.JSONDecodeError as e:
            # This happens when OBS returns invalid/empty JSON
            logger.debug(f'[OBS] Returned invalid JSON. error="{str(e)}"')
            return {"message": "OBS not connected", "connected": False}
        except Exception as e:
            # Check if it's a connection-related error
            error_msg = str(e).lower()
            if (
                "broken pipe" in error_msg
                or "connection" in error_msg
                or "timeout" in error_msg
                or "errno 32" in error_msg
            ):
                logger.info(f'[OBS] Disconnected, will reconnect. error="{str(e)}"')
                self._client_req = None
                self._client_event = None
                await self._schedule_reconnect()
                return {"message": "OBS reconnecting", "connected": False}

            logger.error(f'[OBS] ❌ Unexpected error getting state. error="{str(e)}"')
            return {"message": "OBS state unavailable", "connected": False}

    # Control methods
    async def switch_scene(self, scene_name: str):
        """Switch to a specific scene."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.set_current_program_scene(scene_name)
            logger.info(f"[OBS] Switched scene. name={scene_name}")

        except Exception as e:
            logger.error(
                f'[OBS] ❌ Failed to switch scene. name={scene_name} error="{str(e)}"'
            )
            raise

    async def start_recording(self):
        """Start recording."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.start_record()
            logger.info("[OBS] Recording started.")

        except Exception as e:
            logger.error(f'[OBS] ❌ Failed to start recording. error="{str(e)}"')
            raise

    async def stop_recording(self):
        """Stop recording."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.stop_record()
            logger.info("[OBS] Recording stopped.")

        except Exception as e:
            logger.error(f'[OBS] ❌ Failed to stop recording. error="{str(e)}"')
            raise

    async def start_streaming(self):
        """Start streaming."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.start_stream()
            logger.info("[OBS] Streaming started.")

        except Exception as e:
            logger.error(f'[OBS] ❌ Failed to start streaming. error="{str(e)}"')
            raise

    async def stop_streaming(self):
        """Stop streaming."""
        await self._ensure_running()

        try:
            if not self._client_req:
                raise ConnectionError("Not connected to OBS")

            self._client_req.stop_stream()
            logger.info("[OBS] Streaming stopped.")

        except Exception as e:
            logger.error(f'[OBS] ❌ Failed to stop streaming. error="{str(e)}"')
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
                f"[OBS] Source toggled. source={source_name} scene={scene_name} state={new_state}"
            )

        except Exception as e:
            logger.error(
                f'[OBS] ❌ Failed to toggle source. source={source_name} error="{str(e)}"'
            )
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
            logger.error(f'[OBS] ❌ Failed to get scenes. error="{str(e)}"')
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
            logger.error(
                f'[OBS] ❌ Failed to get sources. scene={scene_name} error="{str(e)}"'
            )
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

            logger.info(f"[OBS] Found browser sources. count={len(browser_sources)}")
            return browser_sources

        except Exception as e:
            logger.error(f'[OBS] ❌ Failed to get browser sources. error="{str(e)}"')
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
                logger.info(f"[OBS] Refreshed browser source. name={source_name}")
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
                logger.info(f"[OBS] Force-refreshed browser source. name={source_name}")
            else:
                logger.warning(
                    f"[OBS] 🟡 Browser source has no URL configured. name={source_name}"
                )

        except Exception as e:
            logger.error(
                f'[OBS] ❌ Failed to refresh browser source. name={source_name} error="{str(e)}"'
            )
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
                    logger.warning(
                        f'[OBS] 🟡 Failed to refresh browser source. name={source["name"]} error="{str(e)}"'
                    )
                    continue

            logger.info(
                f"[OBS] Refreshed browser sources. count={len(browser_sources)}"
            )

            # Broadcast refresh event
            await self._broadcast_event(
                "obs.browser_sources.refreshed",
                {"count": len(browser_sources), "sources": browser_sources},
            )

        except Exception as e:
            logger.error(
                f'[OBS] ❌ Failed to refresh all browser sources. error="{str(e)}"'
            )
            raise

    async def get_stream_performance(self) -> dict | None:
        """Get current streaming performance stats from OBS."""
        await self._ensure_running()

        try:
            if not self._client_req:
                return None

            # Get stream status which includes output frame drops and network congestion
            stream_status = self._client_req.get_stream_status()

            # Get stats which includes render frame drops
            stats = self._client_req.get_stats()

            return {
                "output_active": stream_status.output_active,
                "output_skipped_frames": stream_status.output_skipped_frames,
                "output_total_frames": stream_status.output_total_frames,
                "output_congestion": stream_status.output_congestion or 0.0,
                "render_skipped_frames": stats.render_skipped_frames,
                "render_total_frames": stats.render_total_frames,
            }

        except Exception as e:
            logger.debug(
                f'[Streams] OBS not available for performance check. error="{str(e)}"'
            )
            return None

    async def reset_performance_metrics(self) -> None:
        """Reset OBS performance monitoring state in Redis."""
        await self._ensure_running()

        if not self._redis_client:
            return

        try:
            # Clear all performance-related Redis keys
            await self._redis_client.delete("obs:performance:prev_output_skipped")
            await self._redis_client.delete("obs:performance:prev_output_total")
            await self._redis_client.delete("obs:performance:prev_render_skipped")
            await self._redis_client.delete("obs:performance:prev_render_total")
            await self._redis_client.delete("obs:performance:warning_active")

            logger.info("[Streams] Performance metrics reset.")

        except Exception as e:
            logger.error(
                f'[Streams] ❌ Error resetting performance metrics. error="{str(e)}"'
            )

    async def check_performance_and_alert(self) -> bool:
        """
        Check OBS performance and alert if frame drops exceed threshold.
        Detects three types of issues: rendering lag, network congestion, and encoding lag.
        Uses hysteresis to prevent alert flickering.
        """
        try:
            # Check if monitoring is enabled
            if not settings.OBS_PERFORMANCE_MONITOR_ENABLED:
                return False

            # Get current performance stats
            stats = await self.get_stream_performance()
            if not stats or not stats["output_active"]:
                return False

            # Get previous values from Redis
            if not self._redis_client:
                return False

            prev_output_skipped = await self._redis_client.get(
                "obs:performance:prev_output_skipped"
            )
            prev_output_total = await self._redis_client.get(
                "obs:performance:prev_output_total"
            )
            prev_render_skipped = await self._redis_client.get(
                "obs:performance:prev_render_skipped"
            )
            prev_render_total = await self._redis_client.get(
                "obs:performance:prev_render_total"
            )

            # Calculate deltas for both output and render frames
            output_skipped_delta = stats["output_skipped_frames"] - int(
                (prev_output_skipped or b"0").decode("utf-8")
            )
            output_total_delta = stats["output_total_frames"] - int(
                (prev_output_total or b"0").decode("utf-8")
            )
            render_skipped_delta = stats["render_skipped_frames"] - int(
                (prev_render_skipped or b"0").decode("utf-8")
            )
            render_total_delta = stats["render_total_frames"] - int(
                (prev_render_total or b"0").decode("utf-8")
            )

            # Calculate drop rates
            output_drop_rate = (
                (output_skipped_delta / output_total_delta * 100)
                if output_total_delta > 0
                else 0.0
            )
            render_drop_rate = (
                (render_skipped_delta / render_total_delta * 100)
                if render_total_delta > 0
                else 0.0
            )

            # Store current values for next check (expire after 1 hour)
            await self._redis_client.set(
                "obs:performance:prev_output_skipped",
                stats["output_skipped_frames"],
                ex=3600,
            )
            await self._redis_client.set(
                "obs:performance:prev_output_total",
                stats["output_total_frames"],
                ex=3600,
            )
            await self._redis_client.set(
                "obs:performance:prev_render_skipped",
                stats["render_skipped_frames"],
                ex=3600,
            )
            await self._redis_client.set(
                "obs:performance:prev_render_total",
                stats["render_total_frames"],
                ex=3600,
            )

            # Check if warning is currently active
            warning_active = await self._redis_client.get(
                "obs:performance:warning_active"
            )

            # Hysteresis logic
            trigger_threshold = settings.OBS_FRAME_DROP_THRESHOLD_TRIGGER
            clear_threshold = settings.OBS_FRAME_DROP_THRESHOLD_CLEAR

            # Determine which type of issue is occurring (prioritize render > network > encoding)
            max_drop_rate = max(render_drop_rate, output_drop_rate)

            logger.debug(
                f"[Streams] Performance check. render_drop={render_drop_rate:.2f}% output_drop={output_drop_rate:.2f}% congestion={stats['output_congestion']:.2f}"
            )

            if max_drop_rate >= trigger_threshold and not warning_active:
                # Determine severity
                severity = "minor"
                if max_drop_rate >= 5.0:
                    severity = "critical"
                elif max_drop_rate >= 2.0:
                    severity = "moderate"

                # Determine issue type and generate appropriate message
                if render_drop_rate >= trigger_threshold:
                    issue_type = "rendering_lag"
                    message_text = f"OBS rendering is dropping {render_drop_rate:.1f}% of frames. GPU/compositing cannot keep up."
                    recommendation = "Lower OBS canvas resolution, disable resource-intensive sources, or reduce scene complexity."
                    logger.info(
                        f"[Streams] ⚠️ Rendering lag detected. drop_rate={render_drop_rate:.2f}%"
                    )
                elif (
                    output_drop_rate >= trigger_threshold
                    and stats["output_congestion"] > 0.3
                ):
                    issue_type = "network_congestion"
                    message_text = f"Stream is dropping {output_drop_rate:.1f}% of frames due to network congestion. Poor connection to Twitch ingest server."
                    recommendation = "Check your internet connection or try switching to a different Twitch ingest server."
                    logger.info(
                        f"[Streams] ⚠️ Network congestion detected. drop_rate={output_drop_rate:.2f}% congestion={stats['output_congestion']:.2f}"
                    )
                else:
                    issue_type = "encoding_lag"
                    message_text = f"Stream encoder is dropping {output_drop_rate:.1f}% of frames. CPU/encoder cannot keep up."
                    recommendation = "Lower bitrate, use a faster encoder preset, or close background applications."
                    logger.info(
                        f"[Streams] ⚠️ Encoding lag detected. drop_rate={output_drop_rate:.2f}%"
                    )

                await self._redis_client.set("obs:performance:warning_active", "1")

                # Broadcast warning event
                message = {
                    "event_type": "obs:performance:warning",
                    "source": "obs",
                    "timestamp": timezone.now().isoformat(),
                    "data": {
                        "isWarning": True,
                        "dropRate": round(max_drop_rate, 2),
                        "renderDropRate": round(render_drop_rate, 2),
                        "outputDropRate": round(output_drop_rate, 2),
                        "congestion": round(stats["output_congestion"], 2),
                        "severity": severity,
                        "issueType": issue_type,
                        "message": message_text,
                        "recommendation": recommendation,
                    },
                }
                await self._redis_client.publish(
                    "events:obs", json.dumps(message, default=str)
                )
                return True

            elif max_drop_rate < clear_threshold and warning_active:
                logger.info(
                    f"[Streams] Stream quality recovered. drop_rate={max_drop_rate:.2f}%"
                )
                await self._redis_client.delete("obs:performance:warning_active")

                # Broadcast recovery event
                message = {
                    "event_type": "obs:performance:ok",
                    "source": "obs",
                    "timestamp": timezone.now().isoformat(),
                    "data": {
                        "isWarning": False,
                        "dropRate": round(max_drop_rate, 2),
                        "message": f"Stream quality recovered - frame drops back to normal ({max_drop_rate:.1f}%).",
                    },
                }
                await self._redis_client.publish(
                    "events:obs", json.dumps(message, default=str)
                )
                return True

            return False

        except Exception as e:
            logger.error(
                f'[Streams] ❌ Error checking OBS performance. error="{str(e)}"'
            )
            return False


# Service instance - automatically starts when imported
obs_service = OBSService()
