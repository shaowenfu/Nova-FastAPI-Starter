# /services/websocket_service.py
import json
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, ValidationError

from core.exceptions import WebSocketMessageError, WebSocketConnectionError
from core.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from services.llm import ModelService

logger = get_logger(__name__)


class MessageContent(BaseModel):
    format: Literal["text"] = Field("text", description="Message format")
    content: str = Field(..., description="Plain text content")


class UnifiedWebSocketRequest(BaseModel):
    type: str = Field(..., description="Message type, e.g., ping/status/echo/llm_stream")
    timestamp: datetime = Field(default_factory=datetime.now, description="Client timestamp")
    message: Optional[MessageContent] = Field(None, description="Message body for echo/llm_stream")
    payload: Optional[Dict[str, Any]] = Field(None, description="Custom payload for echo/handlers")
    context: Optional[Dict[str, Any]] = Field(None, description="Extra context fields")
    agent_id: Optional[str] = Field(None, description="Optional agent id for memory namespace")


class PongMessage(BaseModel):
    type: Literal["pong"] = "pong"
    timestamp: str
    data: Dict[str, Any]


class StatusResponse(BaseModel):
    type: Literal["status_response"] = "status_response"
    connected_users: int
    user_id: str
    data: Dict[str, Any]


class TextResponse(BaseModel):
    type: Literal["text_response"] = "text_response"
    content: str
    original_message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class WebSocketError(BaseModel):
    type: Literal["error"] = "error"
    message: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


HandlerResult = Optional[BaseModel | str]
WebSocketHandler = Callable[[str, UnifiedWebSocketRequest], Awaitable[HandlerResult]]


class WebSocketManager:
    """Simple per-user/namespace connection manager."""

    DEFAULT_NAMESPACE = "chat"

    def __init__(self, max_connections: int, max_message_size: int) -> None:
        self._connections: Dict[str, Dict[str, Any]] = {}
        self._connection_count: int = 0
        self._max_connections = max_connections
        self._max_message_size = max_message_size

    async def connect(
        self,
        user_id: str,
        websocket: Any,
        namespace: str = DEFAULT_NAMESPACE,
        subprotocol: Optional[str] = None,
    ) -> None:
        if self._connection_count >= self._max_connections:
            raise WebSocketConnectionError(
                message=f"Max connections reached: {self._max_connections}"
            )

        namespace = namespace or self.DEFAULT_NAMESPACE
        user_connections = self._connections.setdefault(user_id, {})

        if namespace in user_connections:
            logger.warning("User %s duplicated namespace=%s, closing old", user_id, namespace)
            await self.disconnect(user_id, namespace=namespace)

        await websocket.accept(subprotocol=subprotocol)
        user_connections[namespace] = websocket
        self._connection_count += 1
        logger.info(
            "User %s connected namespace=%s, total=%s",
            user_id,
            namespace,
            self._connection_count,
        )

    async def disconnect(self, user_id: str, namespace: Optional[str] = None) -> None:
        if user_id not in self._connections:
            return
        targets = [namespace] if namespace else list(self._connections[user_id].keys())
        for ns in targets:
            ws = self._connections[user_id].get(ns)
            if not ws:
                continue
            try:
                await ws.close()
            except Exception as exc:  # pragma: no cover - log only
                logger.warning("Error closing websocket user=%s ns=%s: %s", user_id, ns, exc)
            finally:
                await self._cleanup_connection(user_id, ns)

    async def _cleanup_connection(self, user_id: str, namespace: str) -> None:
        user_conns = self._connections.get(user_id)
        if not user_conns:
            return
        if namespace in user_conns:
            del user_conns[namespace]
            self._connection_count -= 1
        if not user_conns:
            del self._connections[user_id]

    async def send_message(self, user_id: str, message: str, namespace: str = DEFAULT_NAMESPACE) -> bool:
        ws = self._connections.get(user_id, {}).get(namespace)
        if not ws:
            logger.warning("User %s namespace=%s not connected", user_id, namespace)
            return False
        if len(message.encode("utf-8")) > self._max_message_size:
            raise WebSocketMessageError(message=f"Message exceeds max size {self._max_message_size} bytes")
        try:
            await ws.send_text(message)
            return True
        except Exception as exc:  # pragma: no cover - log only
            logger.error("Send failed user=%s ns=%s: %s", user_id, namespace, exc)
            await self._cleanup_connection(user_id, namespace)
            return False

    def get_connection_count(self) -> int:
        return self._connection_count


class WebSocketService:
    """
    WebSocket 业务逻辑服务，基于 handler registry 进行消息分发。

    内置 handlers:
    - ping: 心跳
    - status: 状态查询
    - echo: 简单回显
    - llm_stream: 通用 LLM 流式对话
    """

    def __init__(
        self,
        model_service: Optional["ModelService"] = None,
        manager: Optional[WebSocketManager] = None,
        max_connections: int = 1000,
        max_message_size: int = 1024 * 1024,
    ):
        self._user_states: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, WebSocketHandler] = {}
        self._model_service: Optional["ModelService"] = model_service
        self._manager = manager or WebSocketManager(
            max_connections=max_connections,
            max_message_size=max_message_size,
        )
        self._register_builtin_handlers()

    async def _send_chat_ws_message(self, user_id: str, payload: str) -> bool:
        """统一的聊天命名空间发送方法."""
        return await self._manager.send_message(user_id, payload, namespace=self._manager.DEFAULT_NAMESPACE)
    def register_handler(self, message_type: str, handler: WebSocketHandler) -> None:
        """注册新的消息处理器，若重复注册则覆盖旧的 handler。"""
        self._handlers[message_type] = handler

    def _register_builtin_handlers(self) -> None:
        self.register_handler("ping", self._handle_ping)
        self.register_handler("status", self._handle_status_request)
        self.register_handler("echo", self._handle_echo)
        self.register_handler("llm_stream", self._handle_llm_stream)

    async def process_message(self, user_id: str, raw_message: str) -> Optional[str]:
        """
        处理WebSocket消息的主入口。
        """
        try:
            unified_request = await self._parse_and_validate_message(raw_message)
            handler = self._handlers.get(unified_request.type)
            if handler is None:
                return WebSocketError(
                    message=f"Unsupported message type: {unified_request.type}",
                    error_code="UNSUPPORTED_MESSAGE_TYPE",
                    timestamp=datetime.now(),
                ).model_dump_json()

            response = await handler(user_id, unified_request)
            if hasattr(response, "model_dump_json"):
                return response.model_dump_json()
            if isinstance(response, str):
                return response
            return None

        except ValidationError as e:
            logger.error(f"用户 {user_id} 消息格式验证失败: {e}")
            error_details = []
            for error in e.errors():
                field_path = " -> ".join(str(loc) for loc in error["loc"])
                error_details.append(f"{field_path}: {error['msg']}")

            error_response = WebSocketError(
                message="消息格式验证失败",
                detail="; ".join(error_details),
                error_code="VALIDATION_ERROR",
            )
            return error_response.model_dump_json()

        except WebSocketMessageError as e:
            logger.error(f"用户 {user_id} WebSocket消息错误: {e}")
            error_response = WebSocketError(
                message=str(e),
                detail=str(e),
                error_code="MESSAGE_ERROR",
            )
            return error_response.model_dump_json()

        except Exception as e:
            logger.error(f"处理用户 {user_id} 消息失败: {e}")
            raise
    
    async def _parse_and_validate_message(self, raw_message: str) -> UnifiedWebSocketRequest:
        """
        解析并验证原始消息
        
        Args:
            raw_message: 原始消息字符串
            
        Returns:
            UnifiedWebSocketRequest: 验证后的统一请求消息模型
            
        Raises:
            WebSocketMessageError: 消息解析失败时抛出
            ValidationError: 消息格式验证失败时抛出
        """
        try:
            message_data = json.loads(raw_message)
        except json.JSONDecodeError as e:
            raise WebSocketMessageError(message=f"Invalid JSON format: {str(e)}")

        if not isinstance(message_data, dict):
            raise WebSocketMessageError(message="Message must be a JSON object")

        return UnifiedWebSocketRequest(**message_data)
    
    async def _handle_ping(self, user_id: str, unified_request: UnifiedWebSocketRequest) -> PongMessage:
        """
        处理心跳检测消息
        
        Args:
            user_id: 用户ID
            unified_request: 统一请求消息模型
            
        Returns:
            PongMessage: 心跳响应消息
        """
        logger.debug(f"收到用户 {user_id} 的心跳检测")
        
        # 更新用户最后活跃时间
        await self._update_user_activity(user_id)
        
        return PongMessage(
            timestamp=unified_request.timestamp.isoformat(),
            data={"server_time": datetime.now().isoformat()}
        )
    async def _handle_status_request(self, user_id: str, unified_request: UnifiedWebSocketRequest) -> StatusResponse:
        """
        处理状态查询请求
        
        Args:
            user_id: 用户ID
            unified_request: 统一请求消息模型
            
        Returns:
            StatusResponse: 状态响应消息
        """
        await self._update_user_activity(user_id)
        return StatusResponse(
            connected_users=self._manager.get_connection_count(),
            user_id=user_id,
            data={
                "user_state": self._user_states.get(user_id, {}),
                "server_time": datetime.now().isoformat(),
            },
        )

    async def _handle_echo(self, user_id: str, unified_request: UnifiedWebSocketRequest) -> TextResponse:
        """通用 echo handler，用于调试 payload/格式。"""
        await self._update_user_activity(user_id)
        content = ""
        if unified_request.message and unified_request.message.content:
            content = unified_request.message.content
        elif unified_request.payload:
            content = json.dumps(unified_request.payload, ensure_ascii=False)
        return TextResponse(
            content=content,
            original_message=content,
            data={"echo": True, "received_at": datetime.now().isoformat()},
        )

    async def _handle_llm_stream(self, user_id: str, unified_request: UnifiedWebSocketRequest) -> None:
        """
        通用 LLM 流式 handler，演示如何集成模型服务 + 可选记忆前置。
        """
        await self._update_user_activity(user_id)
        if not unified_request.message or not unified_request.message.content:
            await self._send_chat_ws_message(
                user_id,
                json.dumps(
                    {
                        "type": "error",
                        "message": "llm_stream requires text content",
                        "error_code": "EMPTY_CONTENT",
                    }
                ),
            )
            return

        user_input = unified_request.message.content.strip()
        model_service = self._get_model_service()
        system_prompt = (
            "You are a helpful AI assistant for early-stage startup teams. "
            "Answer concisely, clarify unknowns, and avoid domain-specific assumptions."
        )

        async for chunk in model_service.generate_response_stream(
            system_prompt=system_prompt,
            user_input=user_input,
        ):
            await self._send_chat_ws_message(
                user_id,
                json.dumps({"type": "llm_stream", "chunk": chunk}),
            )
        await self._send_chat_ws_message(
            user_id,
            json.dumps({"type": "llm_stream_done", "ok": True}),
        )
    
    async def _update_user_activity(self, user_id: str) -> None:
        """
        更新用户活跃状态
        
        Args:
            user_id: 用户ID
        """
        if user_id not in self._user_states:
            self._user_states[user_id] = {}
        
        self._user_states[user_id]["last_activity"] = datetime.now().isoformat()
        self._user_states[user_id]["message_count"] = self._user_states[user_id].get("message_count", 0) + 1
    
    def get_user_state(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 用户状态数据
        """
        return self._user_states.get(user_id, {})
    
    def clear_user_state(self, user_id: str) -> None:
        """
        清理用户状态
        
        Args:
            user_id: 用户ID
        """
        if user_id in self._user_states:
            del self._user_states[user_id]
            logger.debug(f"已清理用户 {user_id} 的状态数据")

    def _get_model_service(self) -> "ModelService":
        """懒加载模型服务，保持与依赖提供者一致。"""
        if self._model_service is None:
            from dependencies.providers import get_config, get_model_service  # 延迟导入避免循环
            self._model_service = get_model_service(get_config())
        return self._model_service


# ===== 单例模式实现 =====


# 全局单例实例
_websocket_service_instance: Optional[WebSocketService] = None


def initialize_websocket_service(model_service: Optional["ModelService"] = None) -> WebSocketService:
    """
    初始化WebSocket服务单例实例。

    Returns:
        WebSocketService: 初始化的WebSocket服务实例

    Note:
        此函数应在应用启动时调用，且只能调用一次。
        可以传入共享的 model_service 供 llm_stream handler 使用。
    """
    global _websocket_service_instance

    if _websocket_service_instance is not None:
        logger.warning("WebSocket服务已经初始化，返回现有实例")
        return _websocket_service_instance

    logger.info("正在初始化WebSocket服务...")
    _websocket_service_instance = WebSocketService(model_service=model_service)
    logger.info("WebSocket服务初始化完成")

    return _websocket_service_instance


def get_websocket_service() -> WebSocketService:
    """
    获取WebSocket服务单例实例
    
    Returns:
        WebSocketService: WebSocket服务实例
        
    Raises:
        RuntimeError: 如果服务未初始化
    """
    global _websocket_service_instance
    
    if _websocket_service_instance is None:
        raise RuntimeError(
            "WebSocket服务未初始化。请确保在应用启动时调用 initialize_websocket_service()"
        )
    
    return _websocket_service_instance


def cleanup_websocket_service() -> None:
    """
    清理WebSocket服务单例实例
    
    Note:
        此函数应在应用关闭时调用
    """
    global _websocket_service_instance
    
    if _websocket_service_instance is not None:
        logger.info("正在清理WebSocket服务...")
        
        # 清理所有用户状态
        _websocket_service_instance._user_states.clear()
        
        # 重置实例
        _websocket_service_instance = None
        
        logger.info("WebSocket服务清理完成")
    else:
        logger.debug("WebSocket服务未初始化，无需清理")
