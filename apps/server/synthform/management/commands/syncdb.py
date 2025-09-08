from __future__ import annotations

import os
import subprocess
import tempfile

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync database from production server"

    def add_arguments(self, parser):
        parser.add_argument(
            "--server",
            default="saya",
            help="Production server hostname (default: saya)",
        )
        parser.add_argument(
            "--container",
            default="synthform-server-1",
            help="Docker container name (default: synthform-server-1)",
        )
        parser.add_argument(
            "--tables", nargs="*", help="Specific tables to sync (default: all)"
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="How many days back to sync (default: 7)",
        )

    def handle(self, *args, **options):
        server = options["server"]
        container = options["container"]
        tables = options["tables"]
        days = options["days"]

        self.stdout.write(f"Syncing database from {server}:{container}")

        # Create temporary file for the dump
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".sql", delete=False
        ) as tmp_file:
            dump_file = tmp_file.name

        try:
            # Generate dump command
            if tables:
                table_args = " ".join([f"--table={table}" for table in tables])
                dump_cmd = f"pg_dump --clean --no-owner --no-privileges {table_args}"
            else:
                # Dump recent data only to avoid huge transfers
                dump_cmd = """pg_dump --clean --no-owner --no-privileges \\
                    --table=events_event \\
                    --table=events_member \\
                    --table=events_token \\
                    --table=streams_session \\
                    --table=audio_session \\
                    --table=audio_chunk \\
                    --table=transcriptions_transcription"""

            # Dump from production
            self.stdout.write("Dumping data from production...")
            result = subprocess.run(
                ["ssh", server, f'docker exec {container} {dump_cmd} "$DATABASE_URL"'],
                stdout=open(dump_file, "w"),
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                self.stderr.write(f"Failed to dump from production: {result.stderr}")
                return

            # Load into local database
            self.stdout.write("Loading data into local database...")

            # Get local database settings
            from django.conf import settings

            db_settings = settings.DATABASES["default"]

            if db_settings["ENGINE"] == "django.db.backends.postgresql":
                # PostgreSQL
                env = os.environ.copy()
                env.update(
                    {
                        "PGDATABASE": db_settings["NAME"],
                        "PGUSER": db_settings["USER"],
                        "PGPASSWORD": db_settings["PASSWORD"],
                        "PGHOST": db_settings["HOST"],
                        "PGPORT": str(db_settings["PORT"]),
                    }
                )

                result = subprocess.run(
                    ["psql", "-f", dump_file], env=env, capture_output=True, text=True
                )

                if result.returncode != 0:
                    self.stderr.write(
                        f"Failed to load into local database: {result.stderr}"
                    )
                    return
            else:
                # SQLite or other - use Django loaddata
                self.stdout.write(
                    "Non-PostgreSQL database detected, using Django loaddata..."
                )
                call_command("loaddata", dump_file)

            self.stdout.write(
                self.style.SUCCESS("Database sync completed successfully!")
            )

        finally:
            # Clean up temp file
            if os.path.exists(dump_file):
                os.unlink(dump_file)
