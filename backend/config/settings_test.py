"""Settings for pytest: works without a .env file."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key")

from .settings import *  # noqa: E402,F403
