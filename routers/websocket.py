# /routers/websocket.py

import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dependencies.auth import get_websocket_user_id
from services.basic.websocket import get_websocket_service
from core.exceptions import (
    WebSocketAuthenticationError,
    WebSocketConnectionError,
    WebSocketMessageError,
    WebSocketTimeoutError,
)
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 聊天端点（通用命名空间）。

    内置 handlers: ping/status/echo/llm_stream。
    如需扩展，可在启动阶段通过 `get_websocket_service().register_handler("your_type", handler)` 注册。
    """
    user_id: Optional[str] = None
    ws_service = None
    try:
        user_id = await get_websocket_user_id(websocket)
        logger.info(f"用户 {user_id} 尝试建立WebSocket连接")
        subprotocol = websocket.scope.get("auth_subprotocol")
        
        # 2. 建立连接
        ws_service = get_websocket_service()
        await ws_service.manager.connect(
            user_id,
            websocket,
            namespace=ws_service.manager.DEFAULT_NAMESPACE,
            subprotocol=subprotocol,
        )
        logger.info(f"用户 {user_id} WebSocket连接建立成功")
        
        # 3. 等待连接稳定后发送连接成功消息
        import asyncio
        await asyncio.sleep(0.1)  # 100ms延迟确保连接稳定
        
        success = await ws_service.manager.send_message(user_id, json.dumps({
            "type": "connection_success",
            "message": "WebSocket连接建立成功",
            "user_id": user_id
        }), namespace=ws_service.manager.DEFAULT_NAMESPACE)
        
        if not success:
            logger.warning(f"用户 {user_id} 连接成功消息发送失败，连接可能已断开")
            return
        
        # 4. 消息循环 - 处理客户端消息
        while True:
            try:
                # 接收客户端消息
                raw_message = await websocket.receive_text()
                logger.debug(f"收到用户 {user_id} 的消息: {raw_message}")
                
                # 处理消息 - 委托给业务服务层（传递原始字符串）
                response_json = await ws_service.process_message(user_id, raw_message)
                
                # 如果有响应，发送给客户端
                if response_json:
                    success = await ws_service.manager.send_message(
                        user_id,
                        response_json,
                        namespace=ws_service.manager.DEFAULT_NAMESPACE,
                    )
                    if not success:
                        logger.warning(f"向用户 {user_id} 发送响应失败，连接可能已断开")
                        break
                
            except WebSocketDisconnect:
                logger.info(f"用户 {user_id} 主动断开WebSocket连接")
                break
            except Exception as e:
                logger.error(f"处理用户 {user_id} 消息时出错: {e}")
                # 尝试发送错误消息给客户端
                error_sent = await ws_service.manager.send_message(user_id, json.dumps({
                    "type": "error",
                    "message": f"消息处理失败: {str(e)}"
                }), namespace=ws_service.manager.DEFAULT_NAMESPACE)
                
                if not error_sent:
                    # 如果发送错误消息失败，说明连接已断开
                    logger.warning(f"向用户 {user_id} 发送错误消息失败，连接已断开")
                    break
    
    except WebSocketAuthenticationError as e:
        logger.warning(f"WebSocket认证失败: {e.message}")
        try:
            await websocket.close(code=4401, reason=e.message)
        except Exception:
            pass
    
    except WebSocketConnectionError as e:
        logger.error(f"WebSocket连接错误: {e.message}")
        try:
            await websocket.close(code=4002, reason=e.message)
        except Exception:
            pass
            
    except RuntimeError as e:
        # Handle specific WebSocket disconnected error that appears as RuntimeError
        if 'WebSocket is not connected. Need to call "accept" first.' in str(e):
            logger.info(f"用户 {user_id} WebSocket连接已断开 (RuntimeError)")
        else:
            logger.error(f"WebSocket处理过程中出现未知RuntimeError: {e}")
            try:
                await websocket.close(code=4000, reason="服务器内部错误")
            except Exception:
                pass
    
    except Exception as e:
        logger.error(f"WebSocket处理过程中出现未知错误: {e}")
        try:
            await websocket.close(code=4000, reason="服务器内部错误")
        except Exception:
            pass
    
    finally:
        # 5. 清理连接
        if user_id and ws_service is not None:
            await ws_service.manager.disconnect(user_id, namespace=ws_service.manager.DEFAULT_NAMESPACE)
            logger.info(f"用户 {user_id} WebSocket连接已清理")
