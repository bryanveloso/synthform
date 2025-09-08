"""
ASGI config for synthform project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

from __future__ import annotations

import asyncio
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
from overlays.consumers import OverlayConsumer  # noqa: E402
from shared.services.twitch.helix import helix_service  # noqa: E402
from streams.services.obs import obs_service  # noqa: E402

django_asgi_app = get_asgi_application()

websocket_urlpatterns = [
    path("ws/events/", EventConsumer.as_asgi()),
    path("ws/overlay/", OverlayConsumer.as_asgi()),
] + audio_websocket_urlpatterns

base_application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)


class ServiceLifecycleASGIApp:
    """ASGI application wrapper that manages service lifecycle (startup/shutdown)."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app
        self._services_started = False

    async def __call__(self, scope, receive, send):
        # Handle lifespan events
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    # Start services on startup
                    if not self._services_started:
                        self._services_started = True
                        asyncio.create_task(obs_service.startup())
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await self._cleanup()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        else:
            # Start services on first non-lifespan request if not started
            if not self._services_started:
                self._services_started = True
                asyncio.create_task(obs_service.startup())
            return await self.asgi_app(scope, receive, send)

    async def _cleanup(self):
        """Clean up services on shutdown."""
        # Close helix service to prevent aiohttp ClientSession warnings
        await helix_service.close()
        # Shutdown OBS service
        await obs_service.shutdown()


application = ServiceLifecycleASGIApp(base_application)
