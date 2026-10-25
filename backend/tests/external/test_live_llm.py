"""Optional smoke test against a REAL provider. Skipped unless LLM_API_KEY is set. Never runs in CI by default."""
import asyncio
import os

import pytest

from app.config import Settings
from app.services.llm import HttpLLM

pytestmark = pytest.mark.external


@pytest.mark.skipif(not os.environ.get("LLM_API_KEY"), reason="LLM_API_KEY not set")
def test_live_provider_round_trip():
    s = Settings.from_env()
    text = asyncio.run(HttpLLM(s).complete("Reply with one word.", [{"role": "user", "content": "Say OK"}], max_tokens=20))
    assert text.strip()
