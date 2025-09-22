"""
URL configuration for synthform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include
from django.urls import path
from ninja import NinjaAPI

from campaigns.api import router as campaigns_router
from games.ffbot.api import router as ffbot_router

from .health import health_check

# Create main API instance
api = NinjaAPI(csrf=False)

# Add routers to main API
api.add_router("/campaigns/", campaigns_router)
api.add_router("/games/ffbot/", ffbot_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    path("events/", include("events.urls")),
    path("api/", api.urls),  # Main API with all routers
]
