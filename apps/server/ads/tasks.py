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
        from asgiref.sync import async_to_sync

        # Check and handle ads/warnings
        result = async_to_sync(ad_scheduler.check_and_run_ad)()

        return result

    except Exception as e:
        logger.error(f"Error in check_ad_schedule task: {e}")
        return False
