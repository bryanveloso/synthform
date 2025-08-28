from __future__ import annotations

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/audio/$", consumers.AudioConsumer.as_asgi()),
    re_path(r"ws/audio/events/$", consumers.EventsConsumer.as_asgi()),
    re_path(r"ws/audio/captions/$", consumers.CaptionsConsumer.as_asgi()),
]
