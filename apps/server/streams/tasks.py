from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def monitor_obs_performance():
    """
    Monitor OBS encoder performance every 5 seconds.
    Checks frame drop rate and triggers alerts when threshold exceeded.
    """
    try:
        import asyncio

        from .services.obs import obs_service

        # Handle event loop properly in forked worker processes
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(obs_service.check_performance_and_alert())
        return result

    except Exception as e:
        logger.error(
            f'[Streams] ❌ Error in monitor_obs_performance task. error="{str(e)}"'
        )
        return False
