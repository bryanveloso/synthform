from __future__ import annotations

from django.apps import AppConfig


class FFBotConfig(AppConfig):
    default_auto_field = "django.db.models.UUIDField"
    name = "games.ffbot"
    label = "ffbot"
    verbose_name = "FFBot"
