from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Callable
from typing import Dict
from typing import Optional

import numpy as np
import websockets
from channels.layers import get_channel_layer
from django.conf import settings

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Django-integrated audio processor using external WhisperLive service."""

    def __init__(self):
        self.websocket = None
        self.channel_layer = get_channel_layer()
        self.running = False
        self.transcription_callback: Optional[Callable] = None
        self.client_uid = str(uuid.uuid4())
        self.connection_task = None

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
                "model": "base",
                "use_vad": True,
            }
            await self.websocket.send(json.dumps(config))
            logger.info(f"Sent configuration to WhisperLive server: {config}")

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

        logger.info("Audio processor stopped")

    async def process_chunk(
        self, audio_data: bytes, sample_rate: int = 48000, channels: int = 2
    ) -> None:
        """Process audio chunk with WhisperLive WebSocket."""
        if not self.running:
            logger.warning("Audio processor not running")
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

            # Convert audio data to format expected by WhisperLive
            audio_array = self._bytes_to_numpy(audio_data, sample_rate, channels)

            # Convert to float32 and send as binary WebSocket message
            audio_float32 = audio_array.astype(np.float32)
            audio_bytes = audio_float32.tobytes()

            # Send binary audio data to WhisperLive
            await self.websocket.send(audio_bytes)
            logger.info(f"Sent {len(audio_bytes)} bytes of audio data to WhisperLive")

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
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
            elif "text" in data and data["text"].strip():
                # Transcription result
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

    async def _handle_transcription(self, text: str):
        """Handle transcription results from WhisperLive."""
        if not text or not text.strip():
            return

        logger.info(f"Transcription: {text[:50]}...")

        # Create transcription event object (matches original Phononmaser format)
        event = TranscriptionEvent(
            text=text.strip(),
            timestamp=time.time(),
            duration=1.5,  # Approximate chunk duration
        )

        # Call external transcription callback if set
        if self.transcription_callback:
            await self.transcription_callback(event)

        # Broadcast to WebSocket channels
        await self.broadcast_transcription(event)

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
            },
        )

        # Send to captions channel
        await self.channel_layer.group_send(
            "captions",
            {
                "type": "caption_event",
                "timestamp": timestamp_ms,
                "text": event.text,
            },
        )


class TranscriptionEvent:
    """Transcription event object matching original Phononmaser format."""

    def __init__(self, text: str, timestamp: float, duration: float = 1.5):
        self.text = text
        self.timestamp = timestamp
        self.duration = duration


# Global processor instances per session
_processors: Dict[str, AudioProcessor] = {}


async def get_audio_processor(session_id: str = "default") -> AudioProcessor:
    """Get or create an audio processor instance for a session."""
    global _processors
    if session_id not in _processors:
        processor = AudioProcessor()
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
