from __future__ import annotations

from django.apps import AppConfig


class QuotesConfig(AppConfig):
    default_auto_field = "django.db.models.UUIDField"
    name = "quotes"
