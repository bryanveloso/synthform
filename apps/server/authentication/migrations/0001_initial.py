# Initial migration for authentication app
from __future__ import annotations

import uuid

import django.utils.timezone
import encrypted_fields.fields
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Token",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "service",
                    models.CharField(db_index=True, default="twitch", max_length=50),
                ),
                ("user_id", models.CharField(db_index=True, max_length=255)),
                ("access_token", encrypted_fields.fields.EncryptedTextField()),
                (
                    "refresh_token",
                    encrypted_fields.fields.EncryptedTextField(blank=True, null=True),
                ),
                ("expires_in", models.IntegerField(default=3600)),
                (
                    "last_refreshed",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["service", "user_id"],
                        name="authenticat_service_4e4f1c_idx",
                    ),
                    models.Index(
                        fields=["last_refreshed"], name="authenticat_last_re_7b8e5c_idx"
                    ),
                ],
            },
        ),
        migrations.AlterUniqueTogether(
            name="token",
            unique_together={("service", "user_id")},
        ),
    ]