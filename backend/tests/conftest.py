"""Shared test fixtures."""

import pytest

from app.config import DataProvider, Env, Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(env=Env.TEST, data_provider=DataProvider.SIMULATOR)