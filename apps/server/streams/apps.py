from __future__ import annotations

from django.apps import AppConfig


class StreamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "streams"

    def ready(self):
        """Initialize the OBS service when Django starts."""
        from . import services  # noqa: F401
        from .services.obs import obs_service  # noqa: F401
