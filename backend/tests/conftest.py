"""
tests/conftest.py
=================
Global pytest fixtures for AURELIUS backend tests.

Fixtures defined here are available to all tests without import.

Milestone 0: Minimal fixtures for scaffold verification.
Milestone 1: Will add:
  - async_client: async TestClient for FastAPI endpoints
  - mock_provider: injectable mock that satisfies MarketDataProvider interface
  - test_settings: Settings instance with test-specific configuration
"""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """
    Declare the anyio backend for pytest-asyncio.
    Using 'asyncio' (not 'trio') for compatibility with FastAPI's test client.
    """
    return "asyncio"
