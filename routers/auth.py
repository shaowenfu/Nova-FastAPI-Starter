"""Authentication router exposing register/login/refresh/logout endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from dependencies.providers import AuthServiceDep, CurrentUserIdDep
from infrastructure.models.user import (
    AccountDeleteRequest,
    LogoutRequest,
    PasswordLoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SmsSendRequest,
    SmsVerificationResponse,
    SmsVerifyRequest,
    TokenPair,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="注册并返回令牌（需手机号+验证码凭证）",
    description="注册流程：先发送并验证短信获取verification_ticket，再携带手机号、用户名、密码和ticket完成注册，直接返回access/refresh token。",
)
async def register_user(
    payload: RegisterRequest,
    auth_service: AuthServiceDep,
) -> TokenPair:
    """Register a new user with verified phone."""

    return await auth_service.register(payload)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="密码登录（用户名或手机号+密码）",
    description="使用用户名或手机号加密码登录，返回access/refresh token。",
)
async def login_user(
    payload: PasswordLoginRequest,
    auth_service: AuthServiceDep,
) -> TokenPair:
    """Authenticate user credentials and issue token pair."""

    return await auth_service.login_with_password(payload)


@router.post(
    "/sms/send",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="发送短信验证码",
    description="根据scene（register/login/account_delete）向指定手机号发送验证码，支持频率限制。",
)
async def send_sms_code(
    payload: SmsSendRequest,
    auth_service: AuthServiceDep,
) -> Response:
    """Send a verification code for the requested scene."""

    await auth_service.send_sms_code(payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sms/verify",
    response_model=SmsVerificationResponse,
    summary="验证短信验证码",
    description="校验验证码：scene=login 时直接返回 TokenPair，scene=register/account_delete 返回一次性 verification_ticket。",
)
async def verify_sms_code(
    payload: SmsVerifyRequest,
    auth_service: AuthServiceDep,
) -> SmsVerificationResponse:
    """Verify SMS code and issue token pair or ticket."""

    return await auth_service.verify_sms_code(payload)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="刷新令牌（一次性刷新策略）",
    description="使用 refresh_token 获取新的 token 对，旧 refresh_token 会立即失效。",
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> TokenPair:
    """Refresh an access token using one-time refresh token semantics."""

    return await auth_service.refresh(payload)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="登出（撤销刷新令牌）",
    description="提交 refresh_token 撤销当前会话的刷新令牌。",
)
async def logout_user(
    payload: LogoutRequest,
    auth_service: AuthServiceDep,
    current_user_id: CurrentUserIdDep,
) -> Response:
    """Invalidate the provided refresh token for the current user."""

    await auth_service.logout(payload, current_user_id=current_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/account/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="注销账号（密码或短信凭证）",
    description="通过当前登录用户身份，使用密码或短信验证码凭证注销账号；需 JWT 鉴权。",
)
async def delete_account(
    payload: AccountDeleteRequest,
    auth_service: AuthServiceDep,
    current_user_id: CurrentUserIdDep,
) -> Response:
    """Deactivate an account after verifying password or SMS ticket."""

    await auth_service.delete_account(payload, user_id=current_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="查询当前用户信息",
    description="通过当前登录用户的身份获取用户信息。",
)
async def get_me(
    auth_service: AuthServiceDep,
    current_user_id: CurrentUserIdDep,
) -> UserResponse:
    """Return the profile of the current user."""

    return await auth_service.get_me(str(current_user_id))
