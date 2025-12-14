"""Core dependency providers for the framework base (auth/DB/LLM/memory/WS)."""

from typing import Annotated, Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import get_logger
from dependencies.auth import get_current_user_id
from infrastructure.db.mysql_client import get_mysql_session
from infrastructure.db.redis_client import get_redis_client
from infrastructure.repositories.user_repository import UserRepository
from services.auth import AuthService, TokenService
from services.llm import ModelService
from services.sms import SmsService

logger = get_logger(__name__)


# -----------------------------------------------------------------
# Config / shared services
# -----------------------------------------------------------------

def get_config():
    """Return global settings instance."""

    return settings


_model_service: Optional[ModelService] = None


def get_model_service(config=None) -> ModelService:
    """Provide a singleton ModelService instance for all requests."""

    global _model_service
    if _model_service is None:
        if config is None:
            config = get_config()
        _model_service = ModelService(config)
    return _model_service


async def close_model_service() -> None:
    """Shutdown hook to close underlying HTTP clients."""

    global _model_service
    if _model_service is not None:
        await _model_service.aclose()
        _model_service = None


# -----------------------------------------------------------------
# Repository providers
# -----------------------------------------------------------------

async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_mysql_session)]
) -> UserRepository:
    """Provide UserRepository bound to a MySQL session."""

    return UserRepository(session)


# -----------------------------------------------------------------
# Auth / token / SMS providers
# -----------------------------------------------------------------

def get_token_service() -> TokenService:
    """Provide the token service used for JWT operations."""

    return TokenService()


class _ConsoleSmsService:
    """Fallback SMS provider that logs codes instead of sending them."""

    async def send_login_code(self, phone: str, code: str) -> None:
        logger.info("Console SMS provider sending code", phone=phone, code=code)


_sms_service_singleton: SmsService | _ConsoleSmsService | None = None


def get_sms_service() -> SmsService | _ConsoleSmsService:
    """Provide SMS service; fall back to console provider if Aliyun is unavailable."""

    global _sms_service_singleton
    if _sms_service_singleton is not None:
        return _sms_service_singleton

    try:
        _sms_service_singleton = SmsService()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Falling back to console SMS provider: %s", exc)
        _sms_service_singleton = _ConsoleSmsService()
    return _sms_service_singleton


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    sms_service: Annotated[SmsService | _ConsoleSmsService, Depends(get_sms_service)],
) -> AuthService:
    """Provide authentication service wiring repository, token, and Redis."""

    redis_client = get_redis_client()
    return AuthService(
        user_repository=user_repository,
        token_service=token_service,
        redis_client=redis_client,
        sms_service=sms_service,
    )


# -----------------------------------------------------------------
# Type aliases for FastAPI Depends
# -----------------------------------------------------------------

UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
SmsServiceDep = Annotated[SmsService | _ConsoleSmsService, Depends(get_sms_service)]
ModelServiceDep = Annotated[ModelService, Depends(get_model_service)]
CurrentUserIdDep = Annotated[str, Depends(get_current_user_id)]
