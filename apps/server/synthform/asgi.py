"""
ASGI config for synthform project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

from __future__ import annotations

import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter
from channels.routing import URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "synthform.settings")
django.setup()

# Import after Django setup
from audio.routing import websocket_urlpatterns as audio_websocket_urlpatterns  # noqa: E402, I001
from events.consumers import EventConsumer  # noqa: E402

django_asgi_app = get_asgi_application()

websocket_urlpatterns = [
    path("ws/events/", EventConsumer.as_asgi()),
] + audio_websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
