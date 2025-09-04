from __future__ import annotations

from django.contrib import admin

from .models import Token


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ("service", "user_id", "is_expired", "expires_at", "created_at")
    list_filter = ("service", "created_at", "last_refreshed")
    search_fields = ("user_id", "service")
    readonly_fields = ("id", "created_at", "updated_at", "is_expired", "expires_at")
    ordering = ["-created_at"]

    def get_form(self, request, obj=None, **kwargs):
        # Don't show actual token values for security
        form = super().get_form(request, obj, **kwargs)
        if obj:
            form.base_fields[
                "access_token"
            ].help_text = "Token is encrypted and hidden for security"
            form.base_fields[
                "refresh_token"
            ].help_text = "Token is encrypted and hidden for security"
        return form
