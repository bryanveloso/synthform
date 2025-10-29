from __future__ import annotations

from django.apps import AppConfig


class IronmonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "games.ironmon"
    label = "ironmon"
    verbose_name = "IronMON"
