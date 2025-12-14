"""
Exception definitions and FastAPI handlers (generic).

Usage:
- Raise subclasses of `BaseAPIException` from services/routers.
- Register `unified_api_exception_handler` + `generic_exception_handler` in FastAPI.
- Extend by creating new subclasses with `status_code`, `code`, `message`.
"""
from __future__ import annotations

import traceback
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse


class BaseAPIException(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Internal server error."
    detail: str = ""

    def __init__(self, message: Optional[str] = None, detail: Optional[str] = None) -> None:
        if message:
            self.message = message
        if detail:
            self.detail = detail
        super().__init__(self.message)


# Service-level errors
class ServiceError(BaseAPIException):
    pass


class DBConfigError(ServiceError):
    status_code = 500
    code = "DB_CONFIG_ERROR"
    message = "Database configuration error."


class LLMServiceError(ServiceError):
    status_code = 502
    code = "LLM_SERVICE_ERROR"
    message = "LLM provider unavailable."


# Auth errors
class UserAlreadyExistsError(BaseAPIException):
    status_code = 400
    code = "USER_ALREADY_EXISTS"
    message = "User already exists."


class InvalidCredentialsError(BaseAPIException):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    message = "Invalid username or password."


class InvalidTokenError(BaseAPIException):
    status_code = 401
    code = "INVALID_TOKEN"
    message = "Token invalid or expired."


class TokenRevokedError(BaseAPIException):
    status_code = 401
    code = "TOKEN_REVOKED"
    message = "Refresh token has been revoked."


class InactiveUserError(BaseAPIException):
    status_code = 403
    code = "USER_INACTIVE"
    message = "User account is inactive."


class TooManyRequestsError(BaseAPIException):
    status_code = 429
    code = "TOO_MANY_REQUESTS"
    message = "Too many requests."


class InvalidVerificationCodeError(BaseAPIException):
    status_code = 400
    code = "INVALID_VERIFICATION_CODE"
    message = "Verification code invalid or expired."


class SmsSendFailedError(BaseAPIException):
    status_code = 502
    code = "SMS_SEND_FAILED"
    message = "Failed to send SMS."


# WebSocket errors
class WebSocketAuthenticationError(BaseAPIException):
    status_code = 401
    code = "WEBSOCKET_AUTH_ERROR"
    message = "WebSocket authentication failed."


class WebSocketConnectionError(BaseAPIException):
    status_code = 400
    code = "WEBSOCKET_CONNECTION_ERROR"
    message = "WebSocket connection error."


class WebSocketMessageError(BaseAPIException):
    status_code = 400
    code = "WEBSOCKET_MESSAGE_ERROR"
    message = "WebSocket message error."


class WebSocketTimeoutError(BaseAPIException):
    status_code = 408
    code = "WEBSOCKET_TIMEOUT_ERROR"
    message = "WebSocket timeout."


# FastAPI handlers
async def unified_api_exception_handler(request: Request, exc: BaseAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "detail": getattr(exc, "detail", None),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Server error.",
            "detail": str(exc),
        },
    )


__all__ = [
    "BaseAPIException",
    "ServiceError",
    "DBConfigError",
    "LLMServiceError",
    "UserAlreadyExistsError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "TokenRevokedError",
    "InactiveUserError",
    "TooManyRequestsError",
    "InvalidVerificationCodeError",
    "SmsSendFailedError",
    "WebSocketAuthenticationError",
    "WebSocketConnectionError",
    "WebSocketMessageError",
    "WebSocketTimeoutError",
    "unified_api_exception_handler",
    "generic_exception_handler",
]
