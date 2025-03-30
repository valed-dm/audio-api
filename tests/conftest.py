from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from fastapi_limiter import FastAPILimiter


@pytest.fixture(autouse=True)
async def setup_rate_limiting() -> AsyncGenerator[None, Any]:
    redis = FakeAsyncRedis()
    await FastAPILimiter.init(redis)
    yield
    await FastAPILimiter.close()
