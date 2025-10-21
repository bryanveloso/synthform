from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field

import numpy as np
import websockets
from channels.layers import get_channel_layer
from django.conf import settings

from .tasks import store_transcription

logger = logging.getLogger(__name__)


@dataclass
class AudioBuffer:
    """Buffer for accumulating audio chunks before processing."""

    chunks: list[tuple[bytes, int, int, float]] = field(
        default_factory=list
    )  # (data, sample_rate, channels, timestamp)
    total_size: int = 0
    start_time: float = 0.0

    def clear(self):
        """Clear the buffer."""
        self.chunks.clear()
        self.total_size = 0
        self.start_time = 0.0

    def add_chunk(self, data: bytes, sample_rate: int, channels: int):
        """Add a chunk to the buffer."""
        timestamp = time.time()
        if not self.chunks:
            self.start_time = timestamp
        self.chunks.append((data, sample_rate, channels, timestamp))
        self.total_size += len(data)

    def get_duration_ms(self) -> int:
        """Get buffer duration in milliseconds."""
        if not self.chunks:
            return 0
        return int((time.time() - self.start_time) * 1000)

    def remove_oldest_chunks(self, target_size: int):
        """Remove oldest chunks until buffer is below target size."""
        while self.total_size > target_size and len(self.chunks) > 1:
            removed_chunk = self.chunks.pop(0)
            self.total_size -= len(removed_chunk[0])
            if not self.chunks:
                self.start_time = 0.0
            elif len(self.chunks) == 1:
                self.start_time = self.chunks[0][3]


class AudioProcessor:
    """Django-integrated audio processor using external WhisperLive service."""

    def __init__(self, session_id: str = None):
        self.websocket = None
        self.channel_layer = get_channel_layer()
        self.running = False
        self.transcription_callback: Callable | None = None
        self.client_uid = str(uuid.uuid4())
        self.session_id = session_id  # Track the actual audio session ID
        self.connection_task = None

        # Buffer for accumulating audio chunks
        self.buffer = AudioBuffer()
        self.buffer_duration_threshold_ms = (
            1500  # Process when buffer reaches 1.5 seconds
        )
        self.max_buffer_size = 10 * 1024 * 1024  # 10MB max buffer size
        self.processing_task = None
        self.last_process_time = 0

        # Track processed segments to avoid duplicates and handle revisions
        # Stores {start_time: {"text": str, "is_final": bool, "update_count": int}}
        self.processed_segments = OrderedDict()
        self.max_processed_segments = (
            100  # Keep only recent segments (about 2.5 minutes)
        )

    async def start(self, session_id: str = "default"):
        """Initialize the WhisperLive WebSocket connection."""
        if not settings.AUDIO_PROCESSING_ENABLED:
            logger.warning("Audio processing disabled in settings")
            return

        try:
            # Parse external URL to get WebSocket URL
            url_parts = settings.WHISPER_EXTERNAL_URL.replace("http://", "").split(":")
            host = url_parts[0]
            port = int(url_parts[1]) if len(url_parts) > 1 else 9090
            ws_url = f"ws://{host}:{port}"

            self.running = True
            # Connect and configure immediately
            await self._ensure_connection(ws_url)
            logger.info(
                f"Audio processor started, connected to WhisperLive at {ws_url}"
            )

        except Exception as e:
            logger.error(f"Failed to start WhisperLive connection: {e}")

    async def _ensure_connection(self, ws_url: str):
        """Ensure WebSocket connection is established."""
        if self.websocket:
            return

        try:
            self.websocket = await websockets.connect(ws_url)
            logger.info("Connected to WhisperLive server")

            # Send initial configuration
            config = {
                "uid": self.client_uid,
                "language": "en",
                "task": "transcribe",
                "model": "medium.en",
                "use_vad": True,
            }
            await self.websocket.send(json.dumps(config))
            logger.info("Connected to WhisperLive and sent config for transcription")

            # Start listening task
            self.connection_task = asyncio.create_task(self._listen_for_messages())

        except Exception as e:
            logger.error(f"WhisperLive connection error: {e}")
            # Properly close websocket on error
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
            self.websocket = None
            raise

    async def _listen_for_messages(self):
        """Listen for messages from WhisperLive."""
        try:
            if self.websocket:
                async for message in self.websocket:
                    await self._handle_whisper_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WhisperLive connection closed")
        except Exception as e:
            logger.error(f"Error listening for messages: {e}")
        finally:
            self.websocket = None

    async def stop(self):
        """Stop the audio processor."""
        self.running = False

        # Close WebSocket connection
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")

        # Cancel connection task
        if self.connection_task and not self.connection_task.done():
            self.connection_task.cancel()

        # Cancel processing task
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()

        # Clear buffer
        self.buffer.clear()

        # Clear processed segments tracking
        self.processed_segments.clear()

        logger.info("Audio processor stopped")

    async def process_chunk(
        self, audio_data: bytes, sample_rate: int = 48000, channels: int = 2
    ) -> None:
        """Add audio chunk to buffer and process when threshold reached."""
        if not self.running:
            logger.warning("Audio processor not running")
            return

        # Add chunk to buffer
        self.buffer.add_chunk(audio_data, sample_rate, channels)

        # Check for buffer overflow and remove oldest chunks if needed
        if self.buffer.total_size > self.max_buffer_size:
            logger.warning(
                f"Audio buffer overflow: {self.buffer.total_size} bytes, removing oldest chunks"
            )
            self.buffer.remove_oldest_chunks(
                self.max_buffer_size // 2
            )  # Remove to 50% capacity

        # Process buffer if duration threshold reached
        buffer_duration = self.buffer.get_duration_ms()
        if buffer_duration >= self.buffer_duration_threshold_ms:
            # Avoid overlapping processing
            if self.processing_task and not self.processing_task.done():
                logger.debug("Previous processing still running, skipping")
                return

            # Start processing task
            self.processing_task = asyncio.create_task(self._process_buffer())

        # Log buffer status periodically
        current_time = time.time()
        if (
            current_time - self.last_process_time > 30.0
        ):  # Log every 30 seconds instead of 5
            logger.info(
                f"Audio buffer: {len(self.buffer.chunks)} chunks, {self.buffer.total_size} bytes, {buffer_duration}ms"
            )
            self.last_process_time = current_time

    async def _process_buffer(self) -> None:
        """Process accumulated audio buffer with WhisperLive."""
        if not self.buffer.chunks:
            return

        try:
            # Ensure connection is established
            url_parts = settings.WHISPER_EXTERNAL_URL.replace("http://", "").split(":")
            host = url_parts[0]
            port = int(url_parts[1]) if len(url_parts) > 1 else 9090
            ws_url = f"ws://{host}:{port}"
            await self._ensure_connection(ws_url)

            if not self.websocket:
                logger.error("Failed to establish WebSocket connection")
                return

            # Combine all chunks in buffer
            combined_audio = []
            for chunk_data, sample_rate, channels, _ in self.buffer.chunks:
                # Convert each chunk to numpy array
                audio_array = self._bytes_to_numpy(chunk_data, sample_rate, channels)
                combined_audio.append(audio_array)

            # Concatenate all audio arrays
            if combined_audio:
                full_audio = np.concatenate(combined_audio)

                # Convert to float32 and send as binary WebSocket message
                audio_float32 = full_audio.astype(np.float32)
                audio_bytes = audio_float32.tobytes()

                # Send binary audio data to WhisperLive
                await self.websocket.send(audio_bytes)
                logger.info(
                    f"Sent {len(audio_bytes)} bytes ({self.buffer.get_duration_ms()}ms) of buffered audio to WhisperLive"
                )
                logger.debug("Waiting for transcription response...")

            # Clear buffer after processing
            self.buffer.clear()

        except Exception as e:
            logger.error(f"Error processing audio buffer: {e}")
            # Reset connection on error and properly close websocket
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
            self.websocket = None

    async def _handle_whisper_message(self, message):
        """Handle messages from WhisperLive WebSocket server."""
        try:
            # Parse message - could be text or JSON
            if isinstance(message, bytes):
                # Skip binary messages
                return

            if not isinstance(message, str):
                logger.warning(f"Unexpected message type: {type(message)}")
                return

            # Parse JSON or treat as plain text
            try:
                data = (
                    json.loads(message)
                    if message.startswith("{")
                    else {"text": message}
                )
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from WhisperLive: {e}, treating as text")
                data = {"text": message}

            # Handle different message types
            if "message" in data:
                # Server status messages
                logger.info(f"WhisperLive server: {data['message']}")
            elif "segments" in data:
                # WhisperLive sends cumulative segments array (all from beginning)
                segments = data.get("segments", [])
                if not segments:
                    return

                # Find the newest segment time to determine what's "old"
                all_start_times = [
                    s.get("start", 0) for s in segments if s.get("text", "").strip()
                ]
                if not all_start_times:
                    return
                newest_segment_time = max(all_start_times)

                # Mark segments as final if they're not the most recent ones
                # (WhisperLive typically refines the last 1-2 segments)
                finality_threshold = (
                    newest_segment_time - 3.0
                )  # Segments older than 3 seconds are final

                for segment in segments:
                    text = segment.get("text", "").strip()
                    if not text:
                        continue

                    start_time = segment.get("start", 0)

                    # Skip very old segments (likely from previous stream)
                    if start_time < newest_segment_time - 30:
                        logger.debug(
                            f"Skipping old segment: start={start_time}, newest={newest_segment_time}"
                        )
                        continue

                    # Determine if this segment should be considered final
                    is_partial = start_time > finality_threshold

                    # Check if we've already processed this segment
                    if start_time in self.processed_segments:
                        existing = self.processed_segments[start_time]

                        # If the existing segment is final, never update it
                        if existing["is_final"]:
                            logger.debug(f"Skipping final segment: start={start_time}")
                            continue

                        # If text hasn't changed, just update finality if needed
                        if existing["text"] == text:
                            if not is_partial and not existing["is_final"]:
                                existing["is_final"] = True
                                logger.debug(
                                    f"Marking segment as final: start={start_time}"
                                )
                            continue

                        # Text has changed and segment is still partial - update it
                        existing["text"] = text
                        existing["update_count"] += 1
                        existing["is_final"] = not is_partial

                        # Send the update
                        await self._handle_transcription(
                            text, segment_id=start_time, is_partial=is_partial
                        )
                        logger.debug(
                            f"Updating {'partial' if is_partial else 'final'} segment: "
                            f"start={start_time}, updates={existing['update_count']}"
                        )
                    else:
                        # New segment - add and send it
                        self.processed_segments[start_time] = {
                            "text": text,
                            "is_final": not is_partial,
                            "update_count": 0,
                        }
                        await self._handle_transcription(
                            text, segment_id=start_time, is_partial=is_partial
                        )
                        logger.debug(
                            f"Processing NEW {'partial' if is_partial else 'final'} segment: "
                            f"start={start_time}, text='{text[:30]}...'"
                        )

                    # Enforce memory bound: remove oldest entry if we exceed max size
                    if len(self.processed_segments) > self.max_processed_segments:
                        self.processed_segments.popitem(last=False)
            elif "text" in data and data["text"].strip():
                # Fallback for plain text response
                await self._handle_transcription(data["text"].strip())

        except Exception as e:
            logger.error(f"Error handling WhisperLive message: {e}")

    def _bytes_to_numpy(
        self, audio_data: bytes, sample_rate: int, channels: int
    ) -> np.ndarray:
        """Convert raw audio bytes to numpy array for WhisperLive."""
        # Assuming 16-bit PCM
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Convert to float32 and normalize
        audio_array = audio_array.astype(np.float32) / 32768.0

        # Handle stereo -> mono conversion
        if channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1)

        # WhisperLive expects 16kHz, resample if needed
        if sample_rate != 16000:
            audio_array = self._resample(audio_array, sample_rate, 16000)

        return audio_array

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Simple resampling using linear interpolation."""
        if orig_sr == target_sr:
            return audio

        duration = len(audio) / orig_sr
        target_length = int(duration * target_sr)

        # Simple linear interpolation
        indices = np.linspace(0, len(audio) - 1, target_length)
        return np.interp(indices, np.arange(len(audio)), audio)

    async def _handle_transcription(
        self, text: str, segment_id: float = None, is_partial: bool = False
    ):
        """Handle transcription results from WhisperLive."""
        if not text or not text.strip():
            return

        logger.info(
            f"Transcription ({'partial' if is_partial else 'final'}): {text[:50]}..."
        )

        # Create transcription event object (matches original Phononmaser format)
        event = TranscriptionEvent(
            text=text.strip(),
            timestamp=time.time(),
            duration=1.5,  # Approximate chunk duration
            segment_id=segment_id,  # WhisperLive segment start time
            is_partial=is_partial,
        )

        # Call external transcription callback if set
        if self.transcription_callback:
            await self.transcription_callback(event)

        # Broadcast to WebSocket channels
        await self.broadcast_transcription(event)

        # Store transcription in database
        try:
            if self.session_id:
                store_transcription.delay(
                    text=event.text,
                    session_id=self.session_id,  # Use actual session ID
                    timestamp=event.timestamp,
                    duration=event.duration,
                )
            else:
                logger.warning(
                    "No session ID available, skipping transcription storage"
                )
        except Exception as e:
            logger.error(f"Failed to queue transcription storage task: {e}")

    async def broadcast_transcription(self, event):
        """Broadcast transcription to WebSocket channels."""
        if not self.channel_layer:
            return

        timestamp_ms = int(event.timestamp * 1000)

        # Send to events channel
        await self.channel_layer.group_send(
            "audio_events",
            {
                "type": "transcription_event",
                "timestamp": timestamp_ms,
                "text": event.text,
                "duration": event.duration,
                "segment_id": event.segment_id,
                "is_partial": event.is_partial,
            },
        )

        # Send to captions channel
        await self.channel_layer.group_send(
            "captions",
            {
                "type": "caption_event",
                "timestamp": timestamp_ms,
                "text": event.text,
                "segment_id": event.segment_id,
                "is_partial": event.is_partial,
            },
        )


class TranscriptionEvent:
    """Transcription event object matching original Phononmaser format."""

    def __init__(
        self,
        text: str,
        timestamp: float,
        duration: float = 1.5,
        segment_id: float = None,
        is_partial: bool = False,
    ):
        self.text = text
        self.timestamp = timestamp
        self.duration = duration
        self.segment_id = segment_id
        self.is_partial = is_partial


# Global processor instances per session
_processors: dict[str, AudioProcessor] = {}


async def get_audio_processor(session_id: str = "default") -> AudioProcessor:
    """Get or create an audio processor instance for a session."""
    global _processors
    if session_id not in _processors:
        processor = AudioProcessor(
            session_id=session_id
        )  # Pass session ID to processor
        try:
            await processor.start(session_id)
            _processors[session_id] = processor
        except Exception:
            # If start fails, clean up the processor
            await processor.stop()
            raise
    return _processors[session_id]


async def cleanup_audio_processor(session_id: str = "default"):
    """Clean up an audio processor instance."""
    global _processors
    if session_id in _processors:
        await _processors[session_id].stop()
        del _processors[session_id]
