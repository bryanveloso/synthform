"""
ASGI config for synthform project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from django.urls import path
from events.consumers import EventConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'synthform.settings')
django_asgi_app = get_asgi_application()

websocket_urlpatterns = [
    path('ws/events/', EventConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
