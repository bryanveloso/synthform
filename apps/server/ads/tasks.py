from __future__ import annotations

import logging

from celery import shared_task

from .services import ad_scheduler

logger = logging.getLogger(__name__)


@shared_task
def check_ad_schedule():
    """
    Check if it's time to run an ad or send warnings.
    This task runs every 10 seconds.
    """
    try:
        import asyncio

        # Handle event loop properly in forked worker processes
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(ad_scheduler.check_and_run_ad())
        return result

    except Exception as e:
        logger.error(f"Error in check_ad_schedule task: {e}")
        return False
