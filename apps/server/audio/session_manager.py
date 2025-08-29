from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from celery import current_app
from django.db import IntegrityError
from django.db import transaction
from asgiref.sync import sync_to_async
from django.utils import timezone

from .models import Session

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Session timeout in minutes
SESSION_TIMEOUT_MINUTES = 15


@sync_to_async
def _get_or_create_active_session_sync() -> Session:
    """Synchronous version for transaction handling."""
    with transaction.atomic():
        try:
            # First try to get existing active session with lock
            session = Session.objects.select_for_update().get(is_active=True)
            logger.info(f"Found existing active session: {session.id}")
            return session
        except Session.DoesNotExist:
            # No active session exists, create one
            try:
                session = Session.objects.create(is_active=True)
                logger.info(f"Created new session: {session.id}")
                return session
            except IntegrityError:
                # Another process created a session, get it
                session = Session.objects.get(is_active=True)
                logger.info(f"Found session created by another process: {session.id}")
                return session


async def get_or_create_active_session() -> Session:
    """Get existing active session or create new one with proper locking."""
    return await _get_or_create_active_session_sync()


async def start_session_timeout(session: Session) -> None:
    """Start 15-minute timeout countdown for session."""
    if not session.is_active:
        logger.info(f"Session {session.id} is already inactive, skipping timeout")
        return

    # Cancel any existing timeout
    if session.timeout_task_id:
        logger.info(
            f"Canceling existing timeout task {session.timeout_task_id} for session {session.id}"
        )
        current_app.control.revoke(session.timeout_task_id, terminate=True)

    # Import at runtime to avoid circular imports
    from .tasks import end_session_after_timeout

    # Schedule timeout task
    eta = timezone.now() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    result = end_session_after_timeout.apply_async(args=[str(session.id)], eta=eta)

    # Update session with timeout info
    session.timeout_task_id = result.id
    session.timeout_started_at = timezone.now()
    await session.asave()

    logger.info(
        f"Started {SESSION_TIMEOUT_MINUTES}-minute timeout for session {session.id} (task: {result.id})"
    )


async def cancel_session_timeout(session: Session) -> None:
    """Cancel pending timeout for session."""
    if not session.timeout_task_id:
        logger.info(f"No active timeout for session {session.id}")
        return

    logger.info(
        f"Canceling timeout task {session.timeout_task_id} for session {session.id}"
    )
    current_app.control.revoke(session.timeout_task_id, terminate=True)

    # Clear timeout info
    session.timeout_task_id = None
    session.timeout_started_at = None
    await session.asave()


async def end_session(session: Session) -> None:
    """Mark session as ended."""
    if not session.is_active:
        logger.info(f"Session {session.id} is already ended")
        return

    logger.info(f"Ending session {session.id}")

    # Cancel any pending timeout
    if session.timeout_task_id:
        current_app.control.revoke(session.timeout_task_id, terminate=True)

    # Mark as ended
    session.is_active = False
    session.ended_at = timezone.now()
    session.timeout_task_id = None
    session.timeout_started_at = None
    await session.asave()

    # Clean up audio processor (import at runtime to avoid circular imports)
    from .processor import cleanup_audio_processor

    await cleanup_audio_processor(str(session.id))
