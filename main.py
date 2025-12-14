from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles

# 从 DB 层导入连接管理函数
from infrastructure.db.mongo_client import connect_to_mongo, close_mongo_connection
from infrastructure.db.mysql_client import connect_to_mysql, close_mysql_connection
from infrastructure.db.redis_client import connect_to_redis, close_redis_connection

# 导入配置、路由等
from core.config import settings
from core.logger import setup_logging
from routers import websocket as websocket_router  # WebSocket 路由
from routers import auth as auth_router  # Auth 路由
from routers import health as health_router  # Health 路由

from services.basic.websocket import initialize_websocket_service, cleanup_websocket_service
from core.memory_adapter import init_memory_adapter
from dependencies.providers import close_model_service

# 全局异常处理
from core.exceptions import BaseAPIException, unified_api_exception_handler, generic_exception_handler

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI 应用的生命周期事件管理器。
    yield 之前的代码在应用启动时执行。
    yield 之后的代码在应用关闭时执行。
    """
    
    # --- 0. 首先配置日志系统 ---
    setup_logging(level="DEBUG", include_timestamp=True)
    
    print(f"[{settings.APP_NAME}] Application Startup Event triggered.")
    
    # --- A. 应用启动 (Startup) 逻辑 ---
    
    # 建立 MongoDB 连接
    await connect_to_mongo()

    # 建立 MySQL 连接
    await connect_to_mysql()

    # 建立 Redis 连接
    await connect_to_redis()

    # 初始化 Mem0 适配器（线程安全，可重复调用）
    init_memory_adapter()
    
    # 初始化 WebSocket 服务（基础版本，无领域耦合）
    initialize_websocket_service()
    print(f"[{settings.APP_NAME}] WebSocket Service initialized.")
    
    # yield 语句将控制权交给 FastAPI，应用开始接受请求
    yield
    
    # --- B. 应用关闭 (Shutdown) 逻辑 ---
    
    print(f"[{settings.APP_NAME}] Application Shutdown Event triggered.")
    
    # 清理 WebSocket 服务
    cleanup_websocket_service()
    print(f"[{settings.APP_NAME}] WebSocket Service cleaned up.")
    
    # 关闭 MongoDB 连接
    await close_mongo_connection()
    
    # 关闭 Redis 连接
    await close_redis_connection()

    # 关闭 MySQL 连接
    await close_mysql_connection()

    # 关闭 LLM 相关客户端（如已使用）
    await close_model_service()


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
Minimal FastAPI starter with JWT Auth + WebSocket base.

- HTTP: /auth/*, /health
- WS: /ws/chat (JWT via Sec-WebSocket-Protocol)
- Static: /static/index.html for samples
""",
    lifespan=lifespan,  # 关键：将生命周期管理器传递给应用
)

# 配置 CORS
# 注意：如果 allow_origins=["*"] 且 allow_credentials=True，部分浏览器会报错。
# 如果是在本地开发遇到跨域问题，建议在 .env 中设置具体的 CORS_ORIGINS，或确保前端没有发送 cookies。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"], # 允许所有方法
    allow_headers=["*"], # 允许所有头（包括 X-Auth-Token）
    allow_credentials=True,
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response
# 配置JWT Bearer Token安全方案，让Swagger UI正确显示Authorization输入框
security = HTTPBearer(
    scheme_name="JWT Bearer Token",
    description="Enter JWT token (without 'Bearer ' prefix)"
)

# 注册 BaseAPIException。任何抛出其子类的异常都会被此处理器捕获。
app.exception_handler(BaseAPIException)(unified_api_exception_handler)
# 注册通用 500 处理器，捕获所有未被处理的 Python 异常
app.exception_handler(Exception)(generic_exception_handler)

# 聚合路由
# 注册 WebSocket、Auth、Health 路由
app.include_router(websocket_router.router)
app.include_router(auth_router.router)
app.include_router(health_router.router)

# 配置静态文件服务 - 使用专门的静态目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 根路径 (可选)
@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME} API. Check /docs for endpoints."}


# 启动服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # 开发模式下启用热重载
    )
