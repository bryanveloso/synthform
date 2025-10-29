from __future__ import annotations

import asyncio
import logging

from django.core.management.base import BaseCommand

from games.ironmon.service import IronMONService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the IronMON TCP server to receive messages from IronMON Connect plugin"

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            type=str,
            default="0.0.0.0",
            help="Host to bind the TCP server to (default: 0.0.0.0)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8080,
            help="Port to bind the TCP server to (default: 8080)",
        )

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]

        self.stdout.write(
            self.style.SUCCESS(f"Starting IronMON TCP server on {host}:{port}")
        )

        service = IronMONService(host=host, port=port)

        try:
            asyncio.run(service.start())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nShutting down..."))
            asyncio.run(service.stop())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error running TCP server: {e}"))
            logger.error(f"Error running IronMON TCP server: {e}", exc_info=True)
            raise
