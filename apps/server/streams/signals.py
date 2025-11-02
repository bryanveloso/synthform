from __future__ import annotations

import json
import logging

import redis
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Status

logger = logging.getLogger(__name__)
redis_client = redis.from_url(settings.REDIS_URL)


@receiver(post_save, sender=Status)
def publish_status_update(sender, instance, created, **kwargs):
    """Publish status updates to Redis when a Status is saved."""
    try:
        event_data = {
            "event_type": "status:update",
            "source": "status",
            "data": {
                "status": instance.status,
                "message": instance.message,
                "updated_at": instance.updated_at.isoformat()
                if instance.updated_at
                else None,
            },
        }

        # Store current status in Redis key for instant access
        redis_client.set("broadcaster:status", instance.status)

        # Publish to Redis channel for real-time updates
        redis_client.publish("events:status", json.dumps(event_data))
        logger.info(
            f'[Status] 📍 Published status update to Redis. status={instance.status} message="{instance.message}"'
        )

    except Exception as e:
        logger.error(
            f'[Status] Failed to publish status update to Redis. error="{str(e)}"'
        )
