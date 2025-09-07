from __future__ import annotations

import logging

from celery import shared_task

from transcriptions.models import Transcription

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
        )

        logger.info(f"Stored transcription {transcription.id}: {text[:50]}...")

    except Exception as e:
        logger.error(f"Error storing transcription: {e}")
