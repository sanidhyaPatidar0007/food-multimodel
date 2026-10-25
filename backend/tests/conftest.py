import os

os.environ.setdefault("FOODVERSE_SKIP_DOTENV", "1")  # tests must never read a developer's real backend/.env

import pytest

from tests.helpers import FakeLLM, make_settings


@pytest.fixture
def make_client():
    """Factory for a TestClient wired to an in-memory DB and a mocked LLM (no network, no credentials)."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.database.repository import Repository
    from app.main import create_app

    opened = []

    def _make(llm=None, raise_server_exceptions=True, **settings_kw):
        app = create_app(make_settings(**settings_kw), llm=llm if llm is not None else FakeLLM(available=False), repo=Repository(":memory:"))
        client = TestClient(app, raise_server_exceptions=raise_server_exceptions)
        client.__enter__()
        opened.append(client)
        return client

    yield _make
    for c in opened:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()
