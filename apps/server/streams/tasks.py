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
        from .services.obs import obs_service

        # Check and handle performance alerts
        result = async_to_sync(obs_service.check_performance_and_alert)()

        return result

    except Exception as e:
        logger.error(
            f'[Streams] ❌ Error in monitor_obs_performance task. error="{str(e)}"'
        )
        return False
