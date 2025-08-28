from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from transcriptions.models import Transcription

from .models import Chunk

logger = logging.getLogger(__name__)


@shared_task
def process_audio_chunk(chunk_id: str):
    """Process audio chunk in background and store results."""
    try:
        chunk = Chunk.objects.get(id=chunk_id)
        chunk.processing_started = timezone.now()
        chunk.save()

        # Note: Real-time processing happens in the WebSocket consumer
        # This task is for logging, storage, and any post-processing

        logger.info(f"Processed audio chunk {chunk_id} ({chunk.data_size} bytes)")

        chunk.processed = True
        chunk.save()

        # Broadcast chunk processed event
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "audio_events",
                {
                    "type": "audio_chunk_event",
                    "timestamp": int(chunk.timestamp.timestamp() * 1000),
                    "source_id": chunk.source_id,
                    "source_name": chunk.source_name,
                    "size": chunk.data_size,
                },
            )

    except Chunk.DoesNotExist:
        logger.error(f"Chunk {chunk_id} not found")
    except Exception as e:
        logger.error(f"Error processing audio chunk {chunk_id}: {e}")


@shared_task
def store_transcription(text: str, session_id: str, timestamp: float, duration: float):
    """Store transcription result in database."""
    try:
        # Create transcription record
        transcription = Transcription.objects.create(
            text=text,
            timestamp=timezone.datetime.fromtimestamp(
                timestamp, tz=timezone.datetime.timezone.utc
            ),
            confidence=1.0,  # WhisperLive doesn't provide confidence scores
            metadata={
                "session_id": session_id,
                "duration": duration,
                "processor": "whisper-live",
            },
        )

        logger.info(f"Stored transcription {transcription.id}: {text[:50]}...")

    except Exception as e:
        logger.error(f"Error storing transcription: {e}")


@shared_task
def cleanup_old_audio_chunks(days_old: int = 7):
    """Clean up old processed audio chunks."""
    try:
        cutoff = timezone.now() - timezone.timedelta(days=days_old)
        deleted_count, _ = Chunk.objects.filter(
            timestamp__lt=cutoff, processed=True
        ).delete()

        logger.info(f"Cleaned up {deleted_count} old audio chunks")

    except Exception as e:
        logger.error(f"Error cleaning up audio chunks: {e}")


@shared_task
def end_session_after_timeout(session_id: str):
    """End session after timeout period expires."""
    from asgiref.sync import async_to_sync

    from .models import Session
    from .session_manager import end_session

    try:
        session = Session.objects.get(id=session_id, is_active=True)

        # Double-check this is the right timeout task
        if not session.timeout_task_id:
            logger.info(f"Session {session_id} timeout was already canceled")
            return

        logger.info(f"Timeout expired for session {session_id}, ending session")
        async_to_sync(end_session)(session)

    except Session.DoesNotExist:
        logger.info(f"Session {session_id} not found or already ended")
    except Exception as e:
        logger.error(f"Error ending session {session_id} after timeout: {e}")
