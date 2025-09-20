"""Campaign app tests."""

# Import all test modules to ensure they're discovered by Django's test runner
from __future__ import annotations

from campaigns.test_campaign_activation import *  # noqa: F401, F403
from campaigns.test_integration import *  # noqa: F401, F403
from campaigns.test_models import *  # noqa: F401, F403
from campaigns.test_services import *  # noqa: F401, F403
from campaigns.test_subathon_mode import *  # noqa: F401, F403
