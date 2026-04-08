"""Unit test configuration.

Sets the minimum required environment variables so that pydantic-settings
can construct the Settings singleton at import time. Unit tests never connect
to a real database — integration tests use the DATABASE_URL from conftest.py.
"""

import os


def pytest_configure(config: object) -> None:
    """Set required env vars before any modules are imported."""
    os.environ.setdefault("DATABASE_URL", "postgresql://unit-test-placeholder/db")
