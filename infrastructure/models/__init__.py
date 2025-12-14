from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from typing import Any

# 确保所有 MongoDB ObjectId 都能被正确转换为字符串
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.str_schema()
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x),
                return_schema=core_schema.str_schema(),
            ),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            # 场景 1: 输入已经是 ObjectId (例如：从 MongoDB 驱动读取)
            return v 
        if isinstance(v, str):
            # 场景 2: 输入是字符串 (例如：从 API 请求接收)
            if ObjectId.is_valid(v):
                return ObjectId(v)
        raise ValueError("Invalid ObjectId")
