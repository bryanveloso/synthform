from __future__ import annotations

import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "synthform.settings")

app = Celery("synthform")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure periodic tasks for ad scheduling
app.conf.beat_schedule = {
    "check-ad-schedule": {
        "task": "ads.tasks.check_ad_schedule",
        "schedule": 10.0,  # Every 10 seconds
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
