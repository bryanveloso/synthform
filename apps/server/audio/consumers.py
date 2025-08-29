from __future__ import annotations

import json
import logging
import struct
from datetime import datetime
from datetime import timezone as dt_timezone

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from .models import Chunk
from .processor import get_audio_processor
from .tasks import process_audio_chunk

logger = logging.getLogger(__name__)


class AudioConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for OBS audio data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None
        self.chunk_count = 0
        self.last_chunk_time = 0

    async def connect(self):
        # Allow unauthenticated connections for OBS plugins on Tailscale network
        await self.accept()

        # Get existing active session or create new one
        from .session_manager import get_or_create_active_session

        self.session = await get_or_create_active_session()
        logger.info(f"Audio WebSocket connected to session: {self.session.id}")

    async def disconnect(self, close_code):
        if self.session:
            # Don't end session - it persists across WebSocket connections
            # Only log the disconnection
            logger.info(f"Audio WebSocket disconnected from session: {self.session.id}")

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            await self._handle_binary_data(bytes_data)
        elif text_data:
            await self._handle_json_data(text_data)

    async def _handle_binary_data(self, data: bytes):
        """Handle binary audio data with header."""
        logger.info(f"Received binary data: {len(data)} bytes")
        if len(data) < 28:
            logger.warning("Received binary data too short for header")
            return

        try:
            # Parse binary header (28 bytes)
            header = struct.unpack("<QLLLLL", data[:28])
            (
                timestamp_ns,
                sample_rate,
                channels,
                bit_depth,
                source_id_len,
                source_name_len,
            ) = header

            # Validate header parameters to prevent buffer overflow
            if not self._validate_audio_params(sample_rate, channels, bit_depth):
                logger.warning(
                    f"Invalid audio params: {sample_rate}Hz, {channels}ch, {bit_depth}bit"
                )
                return

            # Validate string lengths to prevent buffer overflow
            if (
                source_id_len > settings.AUDIO_MAX_STRING_LENGTH
                or source_name_len > settings.AUDIO_MAX_STRING_LENGTH
            ):
                logger.warning(
                    f"String lengths too large: id={source_id_len}, name={source_name_len}"
                )
                return

            # Ensure we have enough data for the strings
            required_len = 28 + source_id_len + source_name_len
            if len(data) < required_len:
                logger.warning(
                    f"Insufficient data: got {len(data)}, need {required_len}"
                )
                return

            offset = 28
            # Safely decode strings with error handling
            try:
                source_id = data[offset : offset + source_id_len].decode(
                    "utf-8", errors="replace"
                )
            except UnicodeDecodeError:
                return

            offset += source_id_len
            try:
                source_name = data[offset : offset + source_name_len].decode(
                    "utf-8", errors="replace"
                )
            except UnicodeDecodeError:
                return

            offset += source_name_len
            audio_data = data[offset:]

            # Validate audio data size (prevent DoS via massive chunks)
            if len(audio_data) > settings.AUDIO_MAX_DATA_SIZE:
                logger.warning(f"Audio data too large: {len(audio_data)} bytes")
                return

        except (struct.error, ValueError, OverflowError) as e:
            logger.warning(f"Invalid binary data format: {e}")
            return

        await self._process_audio(
            timestamp_ns=timestamp_ns,
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=bit_depth,
            source_id=source_id,
            source_name=source_name,
            audio_data=audio_data,
        )

    async def _handle_json_data(self, text_data: str):
        """Handle JSON audio data."""
        try:
            data = json.loads(text_data)
            if data.get("type") != "audio_data":
                return

            format_info = data.get("format", {})
            audio_data = bytes.fromhex(data.get("data", ""))

            await self._process_audio(
                timestamp_ns=data.get("timestamp", 0) * 1000000,  # Convert to ns
                sample_rate=format_info.get("sampleRate", 48000),
                channels=format_info.get("channels", 2),
                bit_depth=format_info.get("bitDepth", 16),
                source_id=data.get("sourceId", "unknown"),
                source_name=data.get("sourceName", "Unknown Source"),
                audio_data=audio_data,
            )
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON data received: {e}")

    def _validate_audio_params(
        self, sample_rate: int, channels: int, bit_depth: int
    ) -> bool:
        """Validate audio parameters to prevent DoS attacks."""
        # Reasonable limits for audio parameters
        if not (8000 <= sample_rate <= 192000):  # 8kHz to 192kHz
            return False
        if not (1 <= channels <= 8):  # Mono to 7.1 surround
            return False
        if bit_depth not in (8, 16, 24, 32):  # Standard bit depths
            return False
        return True

    def _check_rate_limit(self) -> bool:
        """Simple rate limiting to prevent abuse."""
        import time

        current_time = time.time()

        # Reset counter if more than 1 second has passed
        if current_time - self.last_chunk_time > 1.0:
            self.chunk_count = 0

        self.last_chunk_time = current_time
        self.chunk_count += 1

        # Apply configured rate limit
        return self.chunk_count <= settings.AUDIO_RATE_LIMIT_PER_SECOND

    async def _process_audio(
        self,
        timestamp_ns: int,
        sample_rate: int,
        channels: int,
        bit_depth: int,
        source_id: str,
        source_name: str,
        audio_data: bytes,
    ):
        """Process incoming audio chunk."""
        if not self.session:
            return

        # Apply rate limiting
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded, dropping audio chunk")
            return

        # Create chunk record
        chunk = await Chunk.objects.acreate(
            session=self.session,
            timestamp=datetime.fromtimestamp(timestamp_ns / 1e9, tz=dt_timezone.utc),
            source_id=source_id,
            source_name=source_name,
            data_size=len(audio_data),
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=bit_depth,
        )

        # Process with WhisperLive in real-time
        logger.info(f"Getting audio processor for session: {self.session.id}")
        processor = await get_audio_processor(str(self.session.id))
        logger.info(f"Processing audio chunk: {len(audio_data)} bytes")
        await processor.process_chunk(audio_data, sample_rate, channels)

        # Also queue for background processing/storage
        process_audio_chunk.delay(str(chunk.id))


class EventsConsumer(AsyncWebsocketConsumer):
    """Consumer for broadcasting transcription events."""

    async def connect(self):
        # Allow unauthenticated connections for OBS plugins on Tailscale network
        await self.channel_layer.group_add("audio_events", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("audio_events", self.channel_name)

    async def transcription_event(self, event):
        """Send transcription to client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "audio:transcription",
                    "timestamp": event["timestamp"],
                    "text": event["text"],
                    "duration": event.get("duration"),
                }
            )
        )

    async def audio_chunk_event(self, event):
        """Send audio chunk metadata to client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "audio:chunk",
                    "timestamp": event["timestamp"],
                    "source_id": event["source_id"],
                    "source_name": event["source_name"],
                    "size": event["size"],
                }
            )
        )


class CaptionsConsumer(AsyncWebsocketConsumer):
    """Consumer for OBS caption plugin."""

    async def connect(self):
        # Allow unauthenticated connections for OBS plugins on Tailscale network
        await self.channel_layer.group_add("captions", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("captions", self.channel_name)

    async def caption_event(self, event):
        """Send caption to OBS."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "audio:transcription",
                    "timestamp": event["timestamp"],
                    "text": event["text"],
                    "is_final": True,
                }
            )
        )
