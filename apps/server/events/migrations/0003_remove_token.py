# Migration to remove Token model (moved to authentication app)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_remove_event_events_even_correla_2f9f43_idx_and_more"),
        ("authentication", "0002_migrate_tokens_from_events"),  # Ensure data is migrated first
    ]

    operations = [
        migrations.DeleteModel(
            name="Token",
        ),
    ]