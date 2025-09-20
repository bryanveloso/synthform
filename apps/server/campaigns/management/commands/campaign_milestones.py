"""Management command for importing/exporting campaign milestones from/to JSON."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction

from campaigns.models import Campaign
from campaigns.models import Milestone


class Command(BaseCommand):
    """Import/export campaign milestones from/to JSON files."""

    help = "Import or export campaign milestones from/to JSON files"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            type=str,
            choices=["import", "export"],
            help="Import milestones from JSON or export to JSON",
        )

        parser.add_argument("file", type=str, help="Path to JSON file")

        parser.add_argument(
            "--campaign-slug",
            type=str,
            required=True,
            help="Campaign slug to import/export milestones for",
        )

        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing milestones before importing (import only)",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without making changes",
        )

    def handle(self, *args, **options):
        action = options["action"]
        file_path = Path(options["file"])
        campaign_slug = options["campaign_slug"]

        try:
            campaign = Campaign.objects.get(slug=campaign_slug)
        except Campaign.DoesNotExist as err:
            raise CommandError(
                f"Campaign with slug '{campaign_slug}' does not exist"
            ) from err

        if action == "import":
            self._import_milestones(campaign, file_path, options)
        else:
            self._export_milestones(campaign, file_path)

    def _import_milestones(self, campaign: Campaign, file_path: Path, options: dict):
        """Import milestones from JSON file."""
        if not file_path.exists():
            raise CommandError(f"File '{file_path}' does not exist")

        with open(file_path) as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, dict):
            raise CommandError("JSON must be an object with 'milestones' array")

        milestones_data = data.get("milestones", [])
        if not isinstance(milestones_data, list):
            raise CommandError("'milestones' must be an array")

        if options["dry_run"]:
            self.stdout.write("DRY RUN - No changes will be made")
            self.stdout.write(f"Would import {len(milestones_data)} milestones")
            for m in milestones_data:
                self.stdout.write(f"  {m['threshold']:4d}: {m['title']}")
            return

        with transaction.atomic():
            if options["clear"]:
                deleted_count = Milestone.objects.filter(campaign=campaign).delete()[0]
                self.stdout.write(
                    self.style.WARNING(f"Cleared {deleted_count} existing milestones")
                )

            created_count = 0
            updated_count = 0

            for milestone_data in milestones_data:
                # Required fields
                threshold = milestone_data.get("threshold")
                title = milestone_data.get("title")
                description = milestone_data.get("description", "")

                if threshold is None or title is None:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Skipping milestone: missing threshold or title: {milestone_data}"
                        )
                    )
                    continue

                # Optional fields
                defaults = {
                    "title": title,
                    "description": description,
                    "is_unlocked": milestone_data.get("is_unlocked", False),
                    "image_url": milestone_data.get("image_url", ""),
                    "announcement_text": milestone_data.get("announcement_text", ""),
                }

                milestone, created = Milestone.objects.update_or_create(
                    campaign=campaign, threshold=threshold, defaults=defaults
                )

                if created:
                    created_count += 1
                    self.stdout.write(f"Created: {threshold:4d} - {title}")
                else:
                    updated_count += 1
                    self.stdout.write(f"Updated: {threshold:4d} - {title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {created_count} created, {updated_count} updated"
            )
        )

    def _export_milestones(self, campaign: Campaign, file_path: Path):
        """Export milestones to JSON file."""
        milestones = Milestone.objects.filter(campaign=campaign).order_by("threshold")

        milestones_data = []
        for milestone in milestones:
            milestone_dict = {
                "threshold": milestone.threshold,
                "title": milestone.title,
                "description": milestone.description,
                "is_unlocked": milestone.is_unlocked,
            }

            # Only include optional fields if they have values
            if milestone.image_url:
                milestone_dict["image_url"] = milestone.image_url
            if milestone.announcement_text:
                milestone_dict["announcement_text"] = milestone.announcement_text

            milestones_data.append(milestone_dict)

        export_data = {
            "campaign": {
                "name": campaign.name,
                "slug": campaign.slug,
                "description": campaign.description,
            },
            "milestones": milestones_data,
            "metadata": {
                "total_milestones": len(milestones_data),
                "max_threshold": max(m["threshold"] for m in milestones_data)
                if milestones_data
                else 0,
            },
        }

        # Create parent directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {len(milestones_data)} milestones to {file_path}"
            )
        )
