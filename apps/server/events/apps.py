from __future__ import annotations

import asyncio
import logging
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """Start background services when Django is ready."""
        # Only run in the main process (not in migrate, shell, etc.)
        import os
        import sys

        # Log what we're seeing
        logger.info(f"[EventsConfig] ready() called. argv={sys.argv}")
        logger.info(
            f"[EventsConfig] Environment check. server_software={os.environ.get('SERVER_SOFTWARE', 'not set')}"
        )

        # Check if we're running as a server (not migrations, shell, etc)
        # Look for common server patterns
        is_migrate = "migrate" in sys.argv
        is_shell = "shell" in sys.argv
        is_makemigrations = "makemigrations" in sys.argv
        is_collectstatic = "collectstatic" in sys.argv

        # Don't start services during migrations or management commands
        if is_migrate or is_shell or is_makemigrations or is_collectstatic:
            logger.info(
                "[EventsConfig] ⏭️ Skipping background services (management command detected)."
            )
            return

        # Don't start background services in the TwitchIO container
        if os.environ.get("DISABLE_BACKGROUND_SERVICES") == "true":
            logger.info(
                "[EventsConfig] ⏭️ Background services disabled by environment variable."
            )
            return

        # If we get here, we're likely running as a server
        logger.info("[EventsConfig] 🚀 Starting background services.")
        # Start background services in a separate thread to avoid blocking
        thread = threading.Thread(target=self._start_background_services)
        thread.daemon = True
        thread.start()

    def _handle_task_exception(self, loop, context):
        """Handle exceptions from asyncio tasks."""
        logger.error(
            f'[EventsConfig] ❌ Background task exception. error="{context.get("exception", context["message"])}"',
            exc_info=context.get("exception"),
        )

    def _start_background_services(self):
        """Start async background services in a new event loop."""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Set exception handler for the loop
            loop.set_exception_handler(self._handle_task_exception)

            logger.info(
                "[EventsConfig] 🚀 Starting background services from AppConfig."
            )

            # Import here to avoid circular imports
            from audio.services.rme import rme_service
            from events.services.rainwave import rainwave_service
            from streams.services.obs import obs_service

            logger.info("[EventsConfig] Services imported.")

            # Create and run tasks
            tasks = [
                loop.create_task(obs_service.startup()),
                loop.create_task(rainwave_service.start_monitoring()),
                loop.create_task(rme_service.startup()),
            ]
            logger.info(
                '[EventsConfig] Service tasks created. services="OBS, Rainwave, RME/OSC"'
            )

            # Wait for all startup tasks to complete
            results = loop.run_until_complete(
                asyncio.gather(*tasks, return_exceptions=True)
            )

            # Check results and log any failures
            service_names = ["OBS", "Rainwave", "RME/OSC"]
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f'[EventsConfig] ❌ Service failed to start. service={service_names[i]} error="{str(result)}"'
                    )

            logger.info("[EventsConfig] ✅ Background services started.")

            # Keep the loop running for background tasks
            loop.run_forever()

        except Exception as e:
            logger.error(
                f'[EventsConfig] ❌ Failed to start background services. error="{str(e)}"',
                exc_info=True,
            )
