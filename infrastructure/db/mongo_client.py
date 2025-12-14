# infrastructure/db/mongo_client.py

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional, Dict
# 导入核心配置
from core.config import settings 
from core.exceptions import DBConfigError, ServiceError

# 声明全局变量，用于保存客户端实例（单例模式）
mongo_client: Optional[AsyncIOMotorClient] = None
# 多数据库实例管理器
database_instances: Dict[str, AsyncIOMotorDatabase] = {}

async def connect_to_mongo():
    """
    在 FastAPI 应用启动时调用：建立 MongoDB 连接并初始化所有业务域数据库。
    """
    global mongo_client, database_instances
    
    # 验证 MONGO_URI 是否配置
    if not settings.MONGO_URI:
        raise DBConfigError(
            detail="MONGO_URI environment variable is empty or not set"
        )
    
    try:
        # 尝试创建唯一的客户端实例
        mongo_client = AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000, # 连接超时设置
            uuidRepresentation="standard"  # 确保UUID的存储格式统一
        )
        
        # 尝试连接，确保连接成功
        await mongo_client.admin.command('ping') 
        
        # 初始化默认数据库
        default_db_name = settings.MONGO_DATABASE
        database_instances["default"] = mongo_client[default_db_name]
        print(f"--- MongoDB Connected to default database: {default_db_name} ---")
        
    except Exception as e:
        # 可以选择重新抛出异常，阻止应用启动
        raise ServiceError(
            status_code=500,
            code="DB_CONNECTION_ERROR",
            message="Failed to connect to MongoDB",
            detail=str(e)
        )

async def close_mongo_connection():
    """
    在 FastAPI 应用关闭时调用：关闭 MongoDB 连接。
    """
    global mongo_client
    if mongo_client:
        mongo_client.close()
        print("--- MongoDB Disconnected ---")

def get_database(domain: str = "default") -> AsyncIOMotorDatabase:
    """
    供 Repository 层调用：根据业务域获取对应的数据库实例。
    
    Args:
        domain: 业务域名称，如 "user", "chat", "psychology", "agent"
    
    Returns:
        对应业务域的数据库实例
    """
    if not database_instances:
        raise ServiceError(
            status_code=500,
            code="DB_NOT_INITIALIZED",
            message="MongoDB databases have not been initialized. Check application startup."
        )
    
    if domain not in database_instances:
        raise ServiceError(
            status_code=500,
            code="DB_DOMAIN_NOT_FOUND",
            message=f"Database domain '{domain}' not found. Available domains: {list(database_instances.keys())}"
        )
    
    return database_instances[domain]

# 注意：Repository应该使用 get_database(domain) 函数并传入对应的域名
# 例如：get_database("user"), get_database("chat"), get_database("agent") 等