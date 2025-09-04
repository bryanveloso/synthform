# Data migration to move tokens from events.Token to authentication.Token

from django.db import migrations


def migrate_tokens_from_events(apps, schema_editor):
    """Migrate tokens from events app to authentication app."""
    # Get the model classes
    OldToken = apps.get_model("events", "Token")
    NewToken = apps.get_model("authentication", "Token")

    # Migrate each token
    for old_token in OldToken.objects.all():
        # Map platform to service field
        service_map = {
            "twitch": "twitch",
            "youtube": "youtube",
            "discord": "discord",
        }

        # Calculate expires_in from expires_at if available
        expires_in = 3600  # default
        if old_token.expires_at:
            from django.utils import timezone

            delta = old_token.expires_at - timezone.now()
            expires_in = max(int(delta.total_seconds()), 0)

        # Create new token
        NewToken.objects.update_or_create(
            service=service_map.get(old_token.platform, "twitch"),
            user_id=old_token.user_id,
            defaults={
                "access_token": old_token.access_token,
                "refresh_token": old_token.refresh_token,
                "expires_in": expires_in,
                "last_refreshed": old_token.updated_at,
                "created_at": old_token.created_at,
            },
        )


def reverse_migrate_tokens(apps, schema_editor):
    """Reverse migration - move tokens back to events app."""
    OldToken = apps.get_model("events", "Token")
    NewToken = apps.get_model("authentication", "Token")

    # Migrate each token back
    for new_token in NewToken.objects.all():
        # Calculate expires_at from expires_in
        from django.utils import timezone
        import datetime

        expires_at = new_token.last_refreshed + datetime.timedelta(
            seconds=new_token.expires_in
        )

        # Create old token
        OldToken.objects.update_or_create(
            platform=new_token.service,
            user_id=new_token.user_id,
            defaults={
                "access_token": new_token.access_token,
                "refresh_token": new_token.refresh_token,
                "expires_at": expires_at,
                "scopes": [],  # We don't track scopes in the new model
                "created_at": new_token.created_at,
                "updated_at": new_token.last_refreshed,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("events", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(migrate_tokens_from_events, reverse_migrate_tokens),
    ]