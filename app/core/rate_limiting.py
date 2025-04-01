from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from redis.asyncio import Redis


async def init_redis(app: FastAPI) -> None:
    redis = Redis.from_url("redis://localhost:6379")
    await FastAPILimiter.init(redis)
    app.state.redis = redis


async def close_redis(app: FastAPI) -> None:
    await app.state.redis.close()


# Rate limit examples
global_rate_limit = RateLimiter(times=100, minutes=1)  # 100 requests/minute
upload_rate_limit = RateLimiter(times=5, minutes=1)  # 5 uploads/minute
