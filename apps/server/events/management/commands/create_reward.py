"""
Management command to create Twitch channel point rewards tied to your CLIENT_ID.

This allows you to programmatically edit the reward later, since Twitch only allows
editing rewards that were created by your application.
"""

from __future__ import annotations

import asyncio

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError


class Command(BaseCommand):
    help = "Creates a Twitch channel point reward tied to your CLIENT_ID"

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            type=str,
            help="Reward title (max 45 characters)",
        )
        parser.add_argument(
            "--cost",
            type=int,
            help="Channel point cost",
        )
        parser.add_argument(
            "--prompt",
            type=str,
            help="Reward description/prompt (max 200 characters)",
        )
        parser.add_argument(
            "--background-color",
            type=str,
            help="Reward background color (hex code)",
        )
        parser.add_argument(
            "--enabled",
            action="store_true",
            help="Enable the reward immediately",
        )
        parser.add_argument(
            "--skip-queue",
            action="store_true",
            help="Skip the redemption queue (auto-fulfill)",
        )
        parser.add_argument(
            "--max-per-stream",
            type=int,
            help="Max redemptions per stream",
        )
        parser.add_argument(
            "--max-per-user-per-stream",
            type=int,
            help="Max redemptions per user per stream",
        )
        parser.add_argument(
            "--global-cooldown",
            type=int,
            help="Global cooldown in seconds",
        )
        parser.add_argument(
            "--user-input-required",
            action="store_true",
            help="Require user to enter text when redeeming",
        )

    def handle(self, *args, **options):
        # If no title/cost provided, go interactive
        if not options["title"] or not options["cost"]:
            options = self._interactive_prompts()

        asyncio.run(self._async_handle(options))

    def _interactive_prompts(self):
        """Prompt user for reward configuration interactively."""
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("=== Twitch Channel Point Reward Creator ===")
        )
        self.stdout.write("")
        self.stdout.write(
            "This will create a reward tied to your CLIENT_ID so you can edit it later."
        )
        self.stdout.write("")

        options = {}

        # Title (required)
        while True:
            title = input("Reward title (max 45 chars): ").strip()
            if title and len(title) <= 45:
                options["title"] = title
                break
            if len(title) > 45:
                self.stdout.write(
                    self.style.ERROR(f"Title too long ({len(title)} chars)")
                )
            else:
                self.stdout.write(self.style.ERROR("Title is required"))

        # Cost (required)
        while True:
            cost_input = input("Channel point cost: ").strip()
            try:
                cost = int(cost_input)
                if cost > 0:
                    options["cost"] = cost
                    break
                else:
                    self.stdout.write(self.style.ERROR("Cost must be positive"))
            except ValueError:
                self.stdout.write(self.style.ERROR("Please enter a number"))

        # Prompt (optional)
        prompt = input("Description/prompt (optional, press Enter to skip): ").strip()
        options["prompt"] = prompt if prompt else ""

        # Background color (optional)
        color = input("Background color (hex, default #9147FF): ").strip()
        if color and not color.startswith("#"):
            color = f"#{color}"
        options["background_color"] = color if color else "#9147FF"

        # Enabled
        enabled = input("Enable immediately? (Y/n): ").strip().lower()
        options["enabled"] = enabled != "n"

        # Skip queue
        skip_queue = (
            input("Skip redemption queue (auto-fulfill)? (y/N): ").strip().lower()
        )
        options["skip_queue"] = skip_queue == "y"

        # User input required
        user_input = input("Require user to enter text? (y/N): ").strip().lower()
        options["user_input_required"] = user_input == "y"

        # Validate prompt if user input is required
        if options["user_input_required"] and not options["prompt"]:
            self.stdout.write(
                self.style.ERROR("Prompt is required when user input is enabled")
            )
            while True:
                prompt = input("Description/prompt (REQUIRED): ").strip()
                if prompt:
                    options["prompt"] = prompt
                    break
                self.stdout.write(self.style.ERROR("Prompt cannot be empty"))

        # Max per stream
        max_stream = input(
            "Max redemptions per stream (press Enter for unlimited): "
        ).strip()
        if max_stream:
            try:
                options["max_per_stream"] = int(max_stream)
            except ValueError:
                self.stdout.write(self.style.WARNING("Invalid number, skipping"))
                options["max_per_stream"] = None
        else:
            options["max_per_stream"] = None

        # Max per user per stream
        max_user = input(
            "Max per user per stream (press Enter for unlimited): "
        ).strip()
        if max_user:
            try:
                options["max_per_user_per_stream"] = int(max_user)
            except ValueError:
                self.stdout.write(self.style.WARNING("Invalid number, skipping"))
                options["max_per_user_per_stream"] = None
        else:
            options["max_per_user_per_stream"] = None

        # Global cooldown
        cooldown = input("Global cooldown in seconds (press Enter for none): ").strip()
        if cooldown:
            try:
                options["global_cooldown"] = int(cooldown)
            except ValueError:
                self.stdout.write(self.style.WARNING("Invalid number, skipping"))
                options["global_cooldown"] = None
        else:
            options["global_cooldown"] = None

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Review your reward configuration:"))
        self.stdout.write(f"  Title: {options['title']}")
        self.stdout.write(f"  Cost: {options['cost']} points")
        if options["prompt"]:
            self.stdout.write(f"  Prompt: {options['prompt']}")
        self.stdout.write(f"  Background: {options['background_color']}")
        self.stdout.write(f"  Enabled: {options['enabled']}")
        self.stdout.write(f"  Auto-fulfill: {options['skip_queue']}")
        if options["user_input_required"]:
            self.stdout.write("  Requires user input: Yes")
        if options["max_per_stream"] is not None:
            self.stdout.write(f"  Max per stream: {options['max_per_stream']}")
        if options["max_per_user_per_stream"] is not None:
            self.stdout.write(f"  Max per user: {options['max_per_user_per_stream']}")
        if options["global_cooldown"] is not None:
            self.stdout.write(f"  Cooldown: {options['global_cooldown']}s")
        self.stdout.write("")

        confirm = input("Create this reward? (Y/n): ").strip().lower()
        if confirm == "n":
            raise CommandError("Reward creation cancelled by user")

        return options

    async def _async_handle(self, options):
        from shared.services.twitch.helix import helix_service

        self.stdout.write("Initializing Twitch Helix service...")

        # Initialize the service
        success = await helix_service.initialize()
        if not success:
            self.stdout.write(self.style.ERROR("Failed to initialize Helix service"))
            return

        try:
            self.stdout.write(
                self.style.WARNING(
                    f"Creating reward: {options['title']} ({options['cost']} points)"
                )
            )

            # Build reward configuration
            reward_config = {
                "title": options["title"],
                "cost": options["cost"],
                "enabled": options["enabled"],
                "is_redemptions_skip_request_queue": options["skip_queue"],
                "background_color": options["background_color"],
            }

            # Add optional fields
            if options["prompt"]:
                reward_config["prompt"] = options["prompt"]

            if options["user_input_required"]:
                reward_config["is_user_input_required"] = True

            if options["max_per_stream"] is not None:
                reward_config["is_max_per_stream_enabled"] = True
                reward_config["max_per_stream"] = options["max_per_stream"]

            if options["max_per_user_per_stream"] is not None:
                reward_config["is_max_per_user_per_stream_enabled"] = True
                reward_config["max_per_user_per_stream"] = options[
                    "max_per_user_per_stream"
                ]

            if options["global_cooldown"] is not None:
                reward_config["is_global_cooldown_enabled"] = True
                reward_config["global_cooldown_seconds"] = options["global_cooldown"]

            # Create the reward
            reward = await helix_service._broadcaster.create_custom_reward(
                **reward_config
            )

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("✅ Reward created successfully!"))
            self.stdout.write("")
            self.stdout.write(f"Reward ID: {reward.id}")
            self.stdout.write(f"Title: {reward.title}")
            self.stdout.write(f"Cost: {reward.cost} points")
            self.stdout.write(f"Enabled: {reward.is_enabled}")
            self.stdout.write(f"Background: {reward.background_color}")
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(f"💾 Save this reward ID to track it: {reward.id}")
            )
            self.stdout.write("")

            # Check current redemption count
            count = 0
            async for _redemption in reward.fetch_redemptions(status="UNFULFILLED"):
                count += 1

            if count > 0:
                self.stdout.write(f"Current unfulfilled redemptions: {count}")

        except Exception as e:
            # Consider catching more specific exceptions (e.g., TwitchAPIException) when known
            self.stdout.write(self.style.ERROR(f"Error creating reward: {e}"))
        finally:
            await helix_service.close()
            self.stdout.write("Done.")
