from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from transcriptions.models import Transcription

from .models import Session

logger = logging.getLogger(__name__)




@shared_task
def store_transcription(text: str, session_id: str, timestamp: float, duration: float):
    """Store transcription result in database."""
    from datetime import datetime
    from datetime import timezone as dt_timezone

    from django.utils import timezone as django_timezone
    from streams.models import Session as StreamSession

    try:
        # Get or create today's stream session
        today = django_timezone.now().date()
        stream_session, _ = StreamSession.objects.get_or_create(session_date=today)

        # Create transcription record
        transcription = Transcription.objects.create(
            text=text,
            timestamp=datetime.fromtimestamp(timestamp, tz=dt_timezone.utc),
            duration=duration,
            confidence=1.0,  # WhisperLive doesn't provide confidence scores
            session=stream_session,  # Link to the streams.Session via ForeignKey
            legacy_stream_session_id=session_id,  # Store the audio session ID for reference
        )

        logger.info(f"Stored transcription {transcription.id}: {text[:50]}...")

    except Exception as e:
        logger.error(f"Error storing transcription: {e}")




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
