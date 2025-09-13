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
        logger.info(f"EventsConfig.ready() called with argv: {sys.argv}")
        logger.info(f"SERVER_SOFTWARE: {os.environ.get('SERVER_SOFTWARE', 'not set')}")

        # Check if we're running as a server (not migrations, shell, etc)
        # Look for common server patterns
        is_migrate = "migrate" in sys.argv
        is_shell = "shell" in sys.argv
        is_makemigrations = "makemigrations" in sys.argv
        is_collectstatic = "collectstatic" in sys.argv

        # Don't start services during migrations or management commands
        if is_migrate or is_shell or is_makemigrations or is_collectstatic:
            logger.info("⏭️ Skipping background services (management command detected)")
            return

        # If we get here, we're likely running as a server
        logger.info("🚀 Starting background services...")
        # Start background services in a separate thread to avoid blocking
        thread = threading.Thread(target=self._start_background_services)
        thread.daemon = True
        thread.start()

    def _start_background_services(self):
        """Start async background services in a new event loop."""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info("🚀 Starting background services from AppConfig...")

            # Import here to avoid circular imports
            from events.services.rainwave import rainwave_service
            from streams.services.obs import obs_service

            # Create tasks
            tasks = [
                loop.create_task(obs_service.startup()),
                loop.create_task(rainwave_service.start_monitoring()),
            ]

            logger.info("✅ Background services started")

            # Run the event loop
            loop.run_forever()

        except Exception as e:
            logger.error(f"Error starting background services: {e}")
