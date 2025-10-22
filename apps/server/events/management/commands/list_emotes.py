"""
Management command to list all channel emotes with their IDs.
Useful for creating emote ID to name mappings for sprite sheets.
"""

from __future__ import annotations

import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Lists all channel emotes with their Twitch IDs for sprite sheet mapping"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            type=str,
            default="typescript",
            choices=["typescript", "json", "python"],
            help="Output format for the emote mapping",
        )
        parser.add_argument(
            "--include-images",
            action="store_true",
            help="Include image URLs in the output",
        )

    def handle(self, *args, **options):
        # Run the async function
        asyncio.run(self._async_handle(options))

    async def _async_handle(self, options):
        import httpx

        # Try user authentication first
        try:
            import twitchio

            from authentication.services import AuthService

            auth_service = AuthService("twitch")
            tokens = await auth_service.get_all_tokens()

            if tokens:
                # Try to use existing user token
                client = twitchio.Client(
                    client_id=settings.TWITCH_CLIENT_ID,
                    client_secret=settings.TWITCH_CLIENT_SECRET,
                )

                try:
                    await client.add_token(
                        tokens[0]["access_token"], tokens[0].get("refresh_token")
                    )

                    # Prevent TwitchIO from saving tokens (we handle that)
                    async def save_tokens():
                        pass

                    client.save_tokens = save_tokens
                    await client.login()

                    # If we get here, tokens are valid
                    return await self._fetch_emotes_with_client(client, options)

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"User tokens expired: {e}"))
                    self.stdout.write("Falling back to app authentication...")
                    await client.close()
        except Exception:
            pass

        # Fall back to app authentication
        self.stdout.write("Using app authentication...")

        # Get app access token
        async with httpx.AsyncClient() as http_client:
            # Request app access token
            token_response = await http_client.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": settings.TWITCH_CLIENT_ID,
                    "client_secret": settings.TWITCH_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                },
            )

            if token_response.status_code != 200:
                self.stdout.write(
                    self.style.ERROR(f"Failed to get app token: {token_response.text}")
                )
                return

            app_token = token_response.json()["access_token"]

            # Get broadcaster info
            self.stdout.write("Getting broadcaster information...")

            # Use user ID if available, otherwise try to get from username
            broadcaster_id = settings.TWITCH_USER_ID

            if broadcaster_id:
                # We already have the ID, just use it
                self.stdout.write(f"Using configured broadcaster ID: {broadcaster_id}")
            else:
                # Fall back to looking up by username
                channel_name = getattr(settings, "TWITCH_CHANNEL_NAME", "avalonstar")
                user_response = await http_client.get(
                    f"https://api.twitch.tv/helix/users?login={channel_name}",
                    headers={
                        "Authorization": f"Bearer {app_token}",
                        "Client-Id": settings.TWITCH_CLIENT_ID,
                    },
                )

                if user_response.status_code != 200:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to get user info: {user_response.text}"
                        )
                    )
                    return

                users_data = user_response.json()["data"]
                if not users_data:
                    self.stdout.write(
                        self.style.ERROR(f"User {channel_name} not found")
                    )
                    return

                broadcaster = users_data[0]
                broadcaster_id = broadcaster["id"]
                self.stdout.write(f"Broadcaster ID: {broadcaster_id}")

            # Get channel emotes
            self.stdout.write("Fetching channel emotes...")

            emotes_response = await http_client.get(
                f"https://api.twitch.tv/helix/chat/emotes?broadcaster_id={broadcaster_id}",
                headers={
                    "Authorization": f"Bearer {app_token}",
                    "Client-Id": settings.TWITCH_CLIENT_ID,
                },
            )

            if emotes_response.status_code != 200:
                self.stdout.write(
                    self.style.ERROR(f"Failed to get emotes: {emotes_response.text}")
                )
                return

            emotes = emotes_response.json()["data"]

            self._process_emotes(emotes, options)

    async def _fetch_emotes_with_client(self, client, options):
        # Get broadcaster info using TwitchIO's built-in methods
        self.stdout.write("Getting broadcaster information...")

        try:
            # Get the broadcaster user - use ID if available
            if settings.TWITCH_USER_ID:
                users = await client.fetch_users(ids=[int(settings.TWITCH_USER_ID)])
            else:
                channel_name = getattr(settings, "TWITCH_CHANNEL_NAME", "avalonstar")
                users = await client.fetch_users(names=[channel_name])
            if not users:
                self.stdout.write(self.style.ERROR("User not found"))
                await client.close()
                return

            broadcaster = users[0]
            self.stdout.write(f"Broadcaster ID: {broadcaster.id}")

            # Get channel emotes using TwitchIO's HTTP session
            self.stdout.write("Fetching channel emotes...")

            # TwitchIO doesn't have a built-in method for this specific endpoint,
            # but we can use its HTTP session
            response = await client._http.request(
                "GET", f"chat/emotes?broadcaster_id={broadcaster.id}"
            )

            emotes = response.get("data", [])
            self._process_emotes(emotes, options)

        finally:
            # Clean up the connection
            await client.close()

    def _process_emotes(self, emotes, options):
        """Process and output emotes in the requested format."""
        if not emotes:
            self.stdout.write(self.style.WARNING("No channel emotes found"))
            return

        self.stdout.write(self.style.SUCCESS(f"Found {len(emotes)} channel emotes:"))
        self.stdout.write("")

        # Output in requested format
        output_format = options["format"]
        include_images = options["include_images"]

        if output_format == "typescript":
            self._output_typescript(emotes, include_images)
        elif output_format == "json":
            self._output_json(emotes, include_images)
        elif output_format == "python":
            self._output_python(emotes, include_images)

    def _output_typescript(self, emotes, include_images):
        """Output as TypeScript mapping."""
        self.stdout.write("// Emote ID to name mapping for sprite sheets")
        self.stdout.write("export const emoteMapping: Record<string, string> = {")

        for emote in emotes:
            self.stdout.write(f'  "{emote["id"]}": "{emote["name"]}",')

        self.stdout.write("};")

        if include_images:
            self.stdout.write("")
            self.stdout.write("// Emote image URLs (for reference)")
            self.stdout.write("export const emoteImages = {")
            for emote in emotes:
                self.stdout.write(f'  "{emote["name"]}": {{')
                self.stdout.write(f'    "1x": "{emote["images"]["url_1x"]}",')
                self.stdout.write(f'    "2x": "{emote["images"]["url_2x"]}",')
                self.stdout.write(f'    "4x": "{emote["images"]["url_4x"]}",')
                self.stdout.write("  },")
            self.stdout.write("};")

    def _output_json(self, emotes, include_images):
        """Output as JSON."""
        import json

        mapping = {emote["id"]: emote["name"] for emote in emotes}

        if include_images:
            output = {
                "mapping": mapping,
                "images": {emote["name"]: emote["images"] for emote in emotes},
            }
        else:
            output = mapping

        self.stdout.write(json.dumps(output, indent=2))

    def _output_python(self, emotes, include_images):
        """Output as Python dictionary."""
        self.stdout.write("# Emote ID to name mapping for sprite sheets")
        self.stdout.write("EMOTE_MAPPING = {")

        for emote in emotes:
            self.stdout.write(f'    "{emote["id"]}": "{emote["name"]}",')

        self.stdout.write("}")

        if include_images:
            self.stdout.write("")
            self.stdout.write("# Emote image URLs (for reference)")
            self.stdout.write("EMOTE_IMAGES = {")
            for emote in emotes:
                self.stdout.write(f'    "{emote["name"]}": {{')
                self.stdout.write(f'        "1x": "{emote["images"]["url_1x"]}",')
                self.stdout.write(f'        "2x": "{emote["images"]["url_2x"]}",')
                self.stdout.write(f'        "4x": "{emote["images"]["url_4x"]}",')
                self.stdout.write("    },")
            self.stdout.write("}")
