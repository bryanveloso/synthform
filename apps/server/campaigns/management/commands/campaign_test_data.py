"""Management command for generating test campaign data for local development."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from campaigns.models import Campaign, Metric, Milestone
from campaigns.services import campaign_service


class Command(BaseCommand):
    """Generate test campaign data for local development."""

    help = "Generate test campaign data for local development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--campaign-slug",
            type=str,
            default="test-subathon",
            help="Campaign slug (default: test-subathon)",
        )

        parser.add_argument(
            "--subs",
            type=int,
            default=0,
            help="Number of test subscriptions to simulate",
        )

        parser.add_argument(
            "--resubs", type=int, default=0, help="Number of test resubs to simulate"
        )

        parser.add_argument(
            "--bits",
            type=int,
            default=0,
            help="Total bits to simulate (random amounts)",
        )

        parser.add_argument(
            "--votes", action="store_true", help="Generate random FFXIV race votes"
        )

        parser.add_argument(
            "--timer", action="store_true", help="Start the subathon timer"
        )

        parser.add_argument(
            "--clear", action="store_true", help="Clear all test data first"
        )

        parser.add_argument(
            "--activate", action="store_true", help="Activate the test campaign"
        )

    def handle(self, *args, **options):
        campaign_slug = options["campaign_slug"]

        if options["clear"]:
            self._clear_test_data()

        # Get or create test campaign
        campaign = self._get_or_create_campaign(campaign_slug, options["activate"])

        # Generate test milestones
        self._create_test_milestones(campaign)

        # Simulate events
        if options["subs"] > 0:
            self._simulate_subscriptions(campaign, options["subs"])

        if options["resubs"] > 0:
            self._simulate_resubs(campaign, options["resubs"])

        if options["bits"] > 0:
            self._simulate_bits(campaign, options["bits"])

        if options["votes"]:
            self._simulate_votes(campaign)

        if options["timer"]:
            self._start_timer(campaign)

        # Display final stats
        self._display_stats(campaign)

    def _clear_test_data(self):
        """Clear all test campaigns and related data."""
        with transaction.atomic():
            deleted = Campaign.objects.filter(slug__startswith="test-").delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared {deleted[0]} test campaigns")
            )

    def _get_or_create_campaign(self, slug: str, activate: bool) -> Campaign:
        """Get or create a test campaign."""
        campaign, created = Campaign.objects.get_or_create(
            slug=slug,
            defaults={
                "name": "Test Subathon",
                "description": "Local test campaign for development",
                "is_active": activate,
                "timer_mode": True,
                "timer_initial_seconds": 3600,  # 1 hour
                "seconds_per_sub": 180,  # 3 minutes
                "seconds_per_tier2": 360,  # 6 minutes
                "seconds_per_tier3": 600,  # 10 minutes
                "max_timer_seconds": 86400,  # 24 hours cap
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created campaign: {campaign.name}"))
        else:
            if activate and not campaign.is_active:
                # Deactivate other campaigns first
                Campaign.objects.exclude(id=campaign.id).update(is_active=False)
                campaign.is_active = True
                campaign.save()
            self.stdout.write(f"Using existing campaign: {campaign.name}")

        return campaign

    def _create_test_milestones(self, campaign: Campaign):
        """Create test milestones if they don't exist."""
        existing_count = Milestone.objects.filter(campaign=campaign).count()
        if existing_count > 0:
            self.stdout.write(f"Campaign already has {existing_count} milestones")
            return

        test_milestones = [
            (10, "Test Mode Activated", "We're testing the system!"),
            (25, "Quarter Century", "25 subs for the 25th anniversary!"),
            (50, "Halfway to 100", "Keep the momentum going!"),
            (75, "Three Quarters", "Almost at 100!"),
            (100, "Century Mark", "Triple digits achieved!"),
            (150, "150 Strong", "The community is growing!"),
            (200, "Double Century", "200 amazing supporters!"),
        ]

        created_count = 0
        for threshold, title, description in test_milestones:
            Milestone.objects.create(
                campaign=campaign,
                threshold=threshold,
                title=title,
                description=description,
                announcement_text=f"🎉 MILESTONE: {title}!",
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Created {created_count} test milestones")
        )

    def _simulate_subscriptions(self, campaign: Campaign, count: int):
        """Simulate subscription events."""
        from asgiref.sync import async_to_sync

        self.stdout.write(f"Simulating {count} subscriptions...")

        unlocked_milestones = []
        for i in range(count):
            # Random tier distribution: 70% T1, 20% T2, 10% T3
            rand = random.random()
            if rand < 0.7:
                tier = 1
            elif rand < 0.9:
                tier = 2
            else:
                tier = 3

            # 30% chance of being a gift
            is_gift = random.random() < 0.3

            result = async_to_sync(campaign_service.process_subscription)(
                campaign, tier=tier, is_gift=is_gift
            )

            if "milestone_unlocked" in result:
                unlocked_milestones.append(result["milestone_unlocked"])

        if unlocked_milestones:
            self.stdout.write(
                self.style.SUCCESS(f"Unlocked {len(unlocked_milestones)} milestones!")
            )
            for milestone in unlocked_milestones:
                self.stdout.write(f"  - {milestone['threshold']}: {milestone['title']}")

    def _simulate_resubs(self, campaign: Campaign, count: int):
        """Simulate resub events."""
        from asgiref.sync import async_to_sync

        self.stdout.write(f"Simulating {count} resubs...")

        for i in range(count):
            async_to_sync(campaign_service.process_resub)(campaign)

    def _simulate_bits(self, campaign: Campaign, total_bits: int):
        """Simulate bit cheer events."""
        from asgiref.sync import async_to_sync

        self.stdout.write(f"Simulating {total_bits} total bits...")

        remaining = total_bits
        while remaining > 0:
            # Random bit amounts: 100, 500, 1000, 5000
            amounts = [100, 500, 1000, 5000]
            amount = random.choice(amounts)
            if amount > remaining:
                amount = remaining

            async_to_sync(campaign_service.process_bits)(campaign, amount)
            remaining -= amount

    def _simulate_votes(self, campaign: Campaign):
        """Simulate FFXIV race voting."""
        from asgiref.sync import async_to_sync

        races = ["viera", "lalafell", "miqote", "aura", "hrothgar"]
        total_votes = random.randint(50, 200)

        self.stdout.write(f"Simulating {total_votes} race votes...")

        for _ in range(total_votes):
            # Weighted random choice (some races more popular)
            weights = [30, 25, 20, 15, 10]  # Viera most popular
            race = random.choices(races, weights=weights)[0]

            # Random vote weight (1-3)
            vote_weight = random.randint(1, 3)

            async_to_sync(campaign_service.update_vote)(campaign, race, vote_weight)

    def _start_timer(self, campaign: Campaign):
        """Start the subathon timer."""
        from asgiref.sync import async_to_sync

        if not campaign.timer_mode:
            self.stdout.write(
                self.style.WARNING("Campaign doesn't have timer mode enabled")
            )
            return

        result = async_to_sync(campaign_service.start_timer)(campaign)
        if "error" in result:
            self.stdout.write(self.style.ERROR(result["error"]))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Timer started with {result['timer_seconds_remaining']} seconds"
                )
            )

    def _display_stats(self, campaign: Campaign):
        """Display campaign statistics."""
        try:
            metric = Metric.objects.get(campaign=campaign)
        except Metric.DoesNotExist:
            self.stdout.write("No metrics recorded yet")
            return

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Campaign: {campaign.name}"))
        self.stdout.write("=" * 50)

        self.stdout.write(f"Total Subs: {metric.total_subs}")
        self.stdout.write(f"Total Resubs: {metric.total_resubs}")
        self.stdout.write(f"Total Bits: {metric.total_bits}")

        if campaign.timer_mode and metric.timer_started_at:
            hours = metric.timer_seconds_remaining // 3600
            minutes = (metric.timer_seconds_remaining % 3600) // 60
            self.stdout.write(f"Timer: {hours}h {minutes}m remaining")

        # Show voting data if present
        if "ffxiv_votes" in metric.extra_data:
            votes = metric.extra_data["ffxiv_votes"]
            if votes:
                self.stdout.write("\nRace Votes:")
                sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
                for race, count in sorted_votes:
                    self.stdout.write(f"  {race}: {count}")

        # Show unlocked milestones
        unlocked = Milestone.objects.filter(
            campaign=campaign, is_unlocked=True
        ).order_by("threshold")

        if unlocked:
            self.stdout.write(f"\nUnlocked Milestones ({unlocked.count()}):")
            for milestone in unlocked:
                self.stdout.write(f"  ✓ {milestone.threshold}: {milestone.title}")

        # Show next milestone
        next_milestone = (
            Milestone.objects.filter(campaign=campaign, is_unlocked=False)
            .order_by("threshold")
            .first()
        )

        if next_milestone:
            subs_needed = next_milestone.threshold - metric.total_subs
            self.stdout.write(
                f"\nNext: {next_milestone.title} ({subs_needed} subs to go)"
            )
