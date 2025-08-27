from __future__ import annotations

from django.urls import path

from .views import TwitchStatusView

app_name = "events"

urlpatterns = [
    path("twitch/status/", TwitchStatusView.as_view(), name="twitch_status"),
]
