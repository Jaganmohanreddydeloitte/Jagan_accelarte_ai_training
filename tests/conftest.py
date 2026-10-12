"""
Pytest configuration and fixtures for IDAMP pipeline tests.

This file is automatically discovered by pytest and provides
shared fixtures and configuration for all tests.
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture(scope="session")
def test_project_root():
    """Provide the project root directory for tests."""
    return project_root


@pytest.fixture(scope="session")
def test_data_dir(test_project_root):
    """Provide a test data directory."""
    return test_project_root / "data"


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Suppress warnings during test runs
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
