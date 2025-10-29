from __future__ import annotations

from django.contrib import admin

from .models import Challenge
from .models import Checkpoint
from .models import Result
from .models import Seed


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(Checkpoint)
class CheckpointAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "trainer", "order", "challenge"]
    list_filter = ["challenge"]
    search_fields = ["name", "trainer"]
    ordering = ["challenge", "order"]


@admin.register(Seed)
class SeedAdmin(admin.ModelAdmin):
    list_display = ["id", "challenge"]
    list_filter = ["challenge"]
    ordering = ["-id"]


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ["seed", "checkpoint", "result"]
    list_filter = ["result", "checkpoint__challenge"]
    search_fields = ["seed__id", "checkpoint__name"]
    ordering = ["-seed"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("seed", "checkpoint")
