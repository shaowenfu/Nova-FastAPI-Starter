"""Authentication and token management services."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import uuid4

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
import bcrypt
from redis.asyncio import Redis

from core.config import settings
from core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    InvalidVerificationCodeError,
    SmsSendFailedError,
    TooManyRequestsError,
    TokenRevokedError,
    UserAlreadyExistsError,
)
from infrastructure.models.user import (
    AccountDeleteRequest,
    DBUser,
    LogoutRequest,
    PasswordLoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SmsScene,
    SmsSendRequest,
    SmsVerificationResponse,
    SmsVerifyRequest,
    TokenPair,
    UserResponse,
)
from infrastructure.repositories.user_repository import UserRepository
from typing import Optional
from services.sms import SmsService


# bcrypt configuration
BCRYPT_ROUNDS = 12  # Number of hashing rounds (higher = more secure but slower)


@dataclass
class TokenResult:
    """Represents a generated token and its metadata."""

    token: str
    expires_at: datetime
    jti: Optional[str] = None


@dataclass
class TokenPayload:
    """Decoded JWT payload."""

    user_id: str
    token_type: str
    expires_at: datetime
    issued_at: datetime
    jti: Optional[str] = None


class TokenService:
    """Service responsible for encoding and decoding JWT tokens."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        access_expires_minutes: Optional[int] = None,
        refresh_expires_minutes: Optional[int] = None,
        static_access_tokens: Optional[Dict[str, str]] = None,
    ) -> None:
        self._secret_key = secret_key or settings.JWT_SECRET_KEY
        self._algorithm = algorithm or settings.JWT_ALGORITHM
        if not self._secret_key:
            raise InvalidTokenError(message="JWT secret key is not configured.")

        self._access_delta = timedelta(
            minutes=access_expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        self._refresh_delta = timedelta(
            minutes=refresh_expires_minutes or settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
        # 可选：静态 Access Token 白名单，用于测试场景
        self._static_access_tokens = static_access_tokens or settings.STATIC_ACCESS_TOKENS or {}

    def create_access_token(self, user_id: str) -> TokenResult:
        now = datetime.now(timezone.utc)
        expires_at = now + self._access_delta
        payload = {
            "sub": str(user_id),
            "exp": int(expires_at.timestamp()),
            "iat": int(now.timestamp()),
            "type": "access",
        }
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return TokenResult(token=token, expires_at=expires_at)

    def create_refresh_token(self, user_id: str) -> TokenResult:
        now = datetime.now(timezone.utc)
        expires_at = now + self._refresh_delta
        jti = str(uuid4())
        payload = {
            "sub": str(user_id),
            "exp": int(expires_at.timestamp()),
            "iat": int(now.timestamp()),
            "type": "refresh",
            "jti": jti,
        }
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return TokenResult(token=token, expires_at=expires_at, jti=jti)

    def decode_token(self, token: str, expected_type: str) -> TokenPayload:
        # 静态 access token 直通（仅限 access 类型）
        if expected_type == "access" and token in self._static_access_tokens:
            user_id = str(self._static_access_tokens[token])
            now = datetime.now(timezone.utc)
            return TokenPayload(
                user_id=user_id,
                token_type="access",
                expires_at=datetime.max.replace(tzinfo=timezone.utc),
                issued_at=now,
                jti=None,
            )

        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except ExpiredSignatureError as exc:
            raise InvalidTokenError(message="Token has expired.") from exc
        except JWTError as exc:
            raise InvalidTokenError(message="Invalid token signature or payload.") from exc

        token_type = payload.get("type")
        if token_type != expected_type:
            raise InvalidTokenError(message="Token type mismatch.")

        user_id = payload.get("sub")
        if user_id is None:
            raise InvalidTokenError(message="Token payload missing subject.")

        try:
            exp_timestamp = int(payload["exp"])
            iat_timestamp = int(payload["iat"])
        except KeyError as exc:
            raise InvalidTokenError(message="Token payload missing required claim.") from exc
        except (TypeError, ValueError) as exc:
            raise InvalidTokenError(message="Token timestamps are invalid.") from exc

        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        issued_at = datetime.fromtimestamp(iat_timestamp, tz=timezone.utc)

        return TokenPayload(
            user_id=str(user_id),
            token_type=token_type,
            expires_at=expires_at,
            issued_at=issued_at,
            jti=payload.get("jti"),
        )


class AuthService:
    """Core authentication workflows (register, login, refresh, logout, account delete)."""

    def __init__(
        self,
        user_repository: UserRepository,
        token_service: TokenService,
        redis_client: Redis,
        sms_service: SmsService,
    ) -> None:
        self._user_repository = user_repository
        self._token_service = token_service
        self._redis = redis_client
        self._sms_service = sms_service
        self._sms_code_length = settings.SMS_CODE_LENGTH
        self._sms_code_ttl = settings.SMS_CODE_TTL_SECONDS
        self._sms_ticket_ttl = settings.SMS_TICKET_TTL_SECONDS
        self._sms_resend_cooldown = settings.SMS_RESEND_COOLDOWN_SECONDS
        self._sms_max_attempts = settings.SMS_MAX_ATTEMPTS
        self._sms_daily_limit = settings.SMS_DAILY_LIMIT_PER_PHONE

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register(self, payload: RegisterRequest) -> TokenPair:
        """Register a new user after verifying phone ownership."""

        phone_user = await self._ensure_phone_available(payload.phone)
        allowed_user_id = phone_user.id if phone_user and not phone_user.is_active else None
        await self._ensure_username_available(payload.username, allowed_user_id=allowed_user_id)
        self._assert_password_complexity(payload.password)
        await self._consume_ticket(SmsScene.REGISTER, payload.phone, payload.verification_ticket)

        password_hash = self._hash_password(payload.password)
        if phone_user and not phone_user.is_active:
            reactivated = await self._user_repository.reactivate_user(
                user_id=phone_user.id,
                username=payload.username,
                password_hash=password_hash,
                phone_verified_at=datetime.now(timezone.utc),
            )
            if reactivated is None:
                raise UserAlreadyExistsError(detail="用户名或手机号已存在。")
            return await self._issue_token_pair(reactivated.id)

        created = await self._user_repository.create_user(
            username=payload.username,
            phone=payload.phone,
            password_hash=password_hash,
            phone_verified_at=datetime.now(timezone.utc),
        )
        if created is None:
            raise UserAlreadyExistsError(detail="用户名或手机号已存在。")

        return await self._issue_token_pair(created.id)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    async def login_with_password(self, payload: PasswordLoginRequest) -> TokenPair:
        user = await self._user_repository.get_by_identifier(payload.identifier)
        if user is None:
            raise InvalidCredentialsError()

        if not self._verify_password(payload.password, user.password_hash):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        return await self._issue_token_pair(user.id)

    async def verify_sms_code(self, payload: SmsVerifyRequest) -> SmsVerificationResponse:
        """Verify SMS code for a scene and produce token pair or ticket."""

        phone = payload.phone
        record = await self._load_code_record(self._sms_code_key(payload.scene, phone))
        if record is None:
            raise InvalidVerificationCodeError()

        if payload.code.strip() != record["code"]:
            await self._handle_invalid_code_attempt(self._sms_code_key(payload.scene, phone), record)
            raise InvalidVerificationCodeError()

        await self._redis.delete(self._sms_code_key(payload.scene, phone))

        if payload.scene == SmsScene.LOGIN:
            user = await self._user_repository.get_by_phone(phone)
            if user is None:
                raise InvalidCredentialsError(message="手机号未注册。")
            if not user.is_active:
                raise InactiveUserError()
            token_pair = await self._issue_token_pair(user.id)
            return SmsVerificationResponse(outcome="login", token_pair=token_pair)
        elif payload.scene == SmsScene.REGISTER:
            await self._ensure_phone_available(phone)
        else:
            # account delete requires existing active user
            user = await self._user_repository.get_by_phone(phone)
            if user is None:
                raise InvalidCredentialsError(message="手机号未注册。")
            if not user.is_active:
                raise InactiveUserError()

        ticket = self._issue_ticket()
        await self._store_ticket(payload.scene, phone, ticket)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._sms_ticket_ttl)
        return SmsVerificationResponse(
            outcome="ticket",
            verification_ticket=ticket,
            ticket_expires_at=expires_at,
        )

    # ------------------------------------------------------------------
    # SMS send
    # ------------------------------------------------------------------
    async def send_sms_code(self, payload: SmsSendRequest) -> None:
        """Send SMS code for the given scene."""

        phone = payload.phone
        if payload.scene == SmsScene.REGISTER:
            await self._ensure_phone_available(phone)
        else:
            user = await self._user_repository.get_by_phone(phone)
            if user is None:
                raise InvalidCredentialsError(message="手机号未注册。")
            if not user.is_active:
                raise InactiveUserError()

        await self._enforce_sms_limits(payload.scene, phone)

        code = self._generate_verification_code()
        code_key = self._sms_code_key(payload.scene, phone)
        await self._redis.set(code_key, json.dumps({"code": code, "attempts": 0}), ex=self._sms_code_ttl)

        try:
            await self._sms_service.send_login_code(phone=phone, code=code)
        except SmsSendFailedError:
            await self._redis.delete(code_key)
            raise

        await self._redis.set(self._sms_cooldown_key(payload.scene, phone), "1", ex=self._sms_resend_cooldown)
        await self._increment_daily_count(payload.scene, phone)

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        # Generate salt and hash the password
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash using bcrypt."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            # If there's any error (e.g., invalid hash format), return False
            return False

    # ------------------------------------------------------------------
    # Refresh & logout
    # ------------------------------------------------------------------
    async def refresh(self, payload: RefreshTokenRequest) -> TokenPair:
        token_payload = self._token_service.decode_token(payload.refresh_token, "refresh")
        await self._assert_refresh_token_valid(token_payload)
        await self._revoke_refresh_token(token_payload)
        return await self._issue_token_pair(token_payload.user_id)

    async def logout(self, payload: LogoutRequest, current_user_id: str) -> None:
        token_payload = self._token_service.decode_token(payload.refresh_token, "refresh")
        if token_payload.user_id != str(current_user_id):
            raise InvalidTokenError(message="Refresh token does not belong to current user.")

        await self._revoke_refresh_token(token_payload, ensure_exists=True)

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    async def get_me(self, user_id: str) -> UserResponse:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError(message="用户不存在。")
        return UserResponse.model_validate(user)

    # ------------------------------------------------------------------
    # Account deletion (deactivation)
    # ------------------------------------------------------------------
    async def delete_account(self, payload: AccountDeleteRequest, user_id: str) -> None:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError(message="用户不存在。")
        if not user.is_active:
            return  # already inactive, no-op

        if payload.password:
            if not self._verify_password(payload.password, user.password_hash):
                raise InvalidCredentialsError(message="密码错误。")
        else:
            if payload.verification_ticket is None:
                raise InvalidVerificationCodeError()
            await self._consume_ticket(SmsScene.ACCOUNT_DELETE, user.phone, payload.verification_ticket)

        await self._user_repository.set_active(user.id, False)
        await self._revoke_all_refresh_tokens(user.id)

    async def _issue_token_pair(self, user_id: str) -> TokenPair:
        access = self._token_service.create_access_token(user_id)
        refresh = self._token_service.create_refresh_token(user_id)
        await self._store_refresh_token(user_id, refresh)
        return TokenPair(
            access_token=access.token,
            refresh_token=refresh.token,
            access_token_expires_at=access.expires_at,
            refresh_token_expires_at=refresh.expires_at,
        )

    async def _store_refresh_token(self, user_id: str, refresh: TokenResult) -> None:
        if refresh.jti is None:
            raise InvalidTokenError(message="Refresh token missing identifier.")

        ttl = max(1, int((refresh.expires_at - datetime.now(timezone.utc)).total_seconds()))
        key = self._build_refresh_key(user_id, refresh.jti)
        await self._redis.set(key, "1", ex=ttl)

    async def _assert_refresh_token_valid(self, payload: TokenPayload) -> None:
        if payload.jti is None:
            raise InvalidTokenError(message="Refresh token missing identifier.")
        key = self._build_refresh_key(payload.user_id, payload.jti)
        exists = await self._redis.exists(key)
        if exists == 0:
            raise TokenRevokedError()

    async def _revoke_refresh_token(self, payload: TokenPayload, ensure_exists: bool = False) -> None:
        if payload.jti is None:
            raise InvalidTokenError(message="Refresh token missing identifier.")
        key = self._build_refresh_key(payload.user_id, payload.jti)
        removed = await self._redis.delete(key)
        if ensure_exists and removed == 0:
            raise TokenRevokedError()

    @staticmethod
    def _build_refresh_key(user_id: str, jti: str) -> str:
        return f"auth:rt:{user_id}:{jti}"

    def _generate_verification_code(self) -> str:
        value = secrets.randbelow(10**self._sms_code_length)
        return str(value).zfill(self._sms_code_length)

    def _sms_code_key(self, scene: SmsScene, phone: str) -> str:
        return f"auth:sms:code:{scene.value}:{phone}"

    def _sms_cooldown_key(self, scene: SmsScene, phone: str) -> str:
        return f"auth:sms:cooldown:{scene.value}:{phone}"

    def _sms_daily_key(self, scene: SmsScene, phone: str) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"auth:sms:daily:{scene.value}:{phone}:{today}"

    @staticmethod
    def _seconds_until_end_of_day() -> int:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((tomorrow - now).total_seconds()))

    async def _load_code_record(self, key: str) -> Optional[dict]:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            code = str(data["code"])
            attempts = int(data.get("attempts", 0))
            return {"code": code, "attempts": attempts}
        except Exception:
            return None

    async def _handle_invalid_code_attempt(self, code_key: str, record: dict) -> None:
        attempts = int(record.get("attempts", 0)) + 1
        ttl = await self._redis.ttl(code_key)
        expire = self._sms_code_ttl if ttl is None or ttl < 0 else ttl
        if attempts >= self._sms_max_attempts:
            await self._redis.delete(code_key)
        else:
            record["attempts"] = attempts
            await self._redis.set(code_key, json.dumps(record), ex=max(1, expire))

    async def _enforce_sms_limits(self, scene: SmsScene, phone: str) -> None:
        cooldown_exists = await self._redis.exists(self._sms_cooldown_key(scene, phone))
        if cooldown_exists:
            raise TooManyRequestsError(detail="请求过于频繁，请稍后再试。")

        daily_key = self._sms_daily_key(scene, phone)
        daily_count_raw = await self._redis.get(daily_key)
        if daily_count_raw is not None and int(daily_count_raw) >= self._sms_daily_limit:
            raise TooManyRequestsError(detail="当日验证码请求次数已达上限。")

    async def _increment_daily_count(self, scene: SmsScene, phone: str) -> None:
        daily_key = self._sms_daily_key(scene, phone)
        count = await self._redis.incr(daily_key)
        if count == 1:
            await self._redis.expire(daily_key, self._seconds_until_end_of_day())

    def _issue_ticket(self) -> str:
        return secrets.token_urlsafe(16)

    async def _store_ticket(self, scene: SmsScene, phone: str, ticket: str) -> None:
        key = self._sms_ticket_key(scene, phone, ticket)
        await self._redis.set(key, "1", ex=self._sms_ticket_ttl)

    async def _consume_ticket(self, scene: SmsScene, phone: str, ticket: str) -> None:
        key = self._sms_ticket_key(scene, phone, ticket)
        removed = await self._redis.delete(key)
        if removed == 0:
            raise InvalidVerificationCodeError(message="验证码凭证无效或已过期。")

    def _sms_ticket_key(self, scene: SmsScene, phone: str, ticket: str) -> str:
        return f"auth:sms:ticket:{scene.value}:{phone}:{ticket}"

    async def _ensure_phone_available(self, phone: str) -> Optional[DBUser]:
        """
        Ensure the phone is not bound to an active account.
        Returns the existing user (may be inactive) for reuse.
        """
        existing_phone = await self._user_repository.get_by_phone(phone)
        if existing_phone is not None and existing_phone.is_active:
            raise UserAlreadyExistsError(detail="手机号已被注册。")
        return existing_phone

    async def _ensure_username_available(self, username: str, allowed_user_id: Optional[str] = None) -> None:
        """
        Ensure username is available. `allowed_user_id` lets an inactive user reuse their own username.
        """
        existing_username = await self._user_repository.get_by_username(username)
        if existing_username is not None and existing_username.id != allowed_user_id:
            raise UserAlreadyExistsError(detail="用户名已存在。")

    def _assert_password_complexity(self, password: str) -> None:
        if len(password) < 6:
            raise InvalidCredentialsError(message="密码长度需不小于6位。")
        has_alpha_or_digit = any(ch.isalpha() for ch in password) or any(ch.isdigit() for ch in password)
        has_symbol = any(not ch.isalnum() for ch in password)
        if not (has_alpha_or_digit and has_symbol):
            raise InvalidCredentialsError(message="密码需包含字母或数字中的至少一种，且至少包含一个符号。")

    async def _revoke_all_refresh_tokens(self, user_id: str) -> None:
        pattern = f"auth:rt:{user_id}:*"
        async for key in self._redis.scan_iter(match=pattern):
            await self._redis.delete(key)
