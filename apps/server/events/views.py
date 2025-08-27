from __future__ import annotations

from django.http import JsonResponse
from django.views import View

from .models import Event
from .models import Member


class TwitchStatusView(View):
    """Health check endpoint for Twitch integration status."""

    def get(self, request):
        """Return status of TwitchIO service and recent events."""
        # Get recent events count
        recent_events = Event.objects.filter(source="twitch").count()
        total_members = Member.objects.count()

        return JsonResponse(
            {
                "status": "running",
                "service_type": "separate_process",
                "recent_events": recent_events,
                "total_members": total_members,
            }
        )
