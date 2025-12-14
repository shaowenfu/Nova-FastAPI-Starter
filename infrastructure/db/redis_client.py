# infrastructure/db/redis_client.py

import redis.asyncio as redis
from typing import Optional
from core.config import settings 

# 全局客户端实例（单例）
redis_client: Optional[redis.Redis] = None

async def connect_to_redis():
    """
    在 FastAPI 应用启动时调用：建立 Redis 连接。
    """
    global redis_client
    
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
    if settings.REDIS_PASSWORD:
        redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}"

    try:
        redis_client = redis.from_url(
            redis_url,
            decode_responses=True # 自动将响应（如键值）解码为字符串
        )
        # 尝试 ping 服务器以测试连接
        await redis_client.ping()
        print("--- Redis Connected ---")
        
    except Exception as e:
        print(f"*** ERROR: Could not connect to Redis: {e} ***")
        raise e

async def close_redis_connection():
    """
    在 FastAPI 应用关闭时调用：关闭 Redis 连接。
    """
    global redis_client
    if redis_client:
        await redis_client.close()
        print("--- Redis Disconnected ---")

def get_redis_client() -> redis.Redis:
    """
    供其他层（如 Service 或 Cache Repository）调用：获取唯一的 Redis 客户端实例。
    """
    if redis_client is None:
        raise ConnectionError("Redis client has not been initialized.")
    return redis_client