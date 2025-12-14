"""Aliyun SMS service wrapper for sending login verification codes."""

from __future__ import annotations

import json
from typing import Optional

try:  # Lazy import to keep tests runnable without Aliyun SDK installed.
    from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
    from alibabacloud_dysmsapi20170525 import models as dysms_models
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as util_models
    _SMS_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - exercised only when SDK missing
    DysmsClient = None
    dysms_models = None
    open_api_models = None
    util_models = None
    _SMS_IMPORT_ERROR = exc

from core.config import settings
from core.exceptions import SmsSendFailedError
from core.logger import get_logger

logger = get_logger(__name__)

# Shared Aliyun client to reuse credential caching and connections.
_shared_dysms_client: Optional["DysmsClient"] = None


class SmsService:
    """Encapsulates Aliyun SMS sending for login verification codes."""

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        sign_name: Optional[str] = None,
        template_code: Optional[str] = None,
        region: Optional[str] = None,
        client: Optional[DysmsClient] = None,
    ) -> None:
        # Use generic SMS_ config keys
        self._access_key_id = access_key_id or settings.SMS_ACCESS_KEY_ID
        self._access_key_secret = access_key_secret or settings.SMS_ACCESS_KEY_SECRET
        self._sign_name = sign_name or settings.SMS_SIGN_NAME
        self._template_code = template_code or settings.SMS_TEMPLATE_CODE
        self._region = region or settings.SMS_REGION
        self._client = client

        if self._client is None and _SMS_IMPORT_ERROR is not None:
            raise SmsSendFailedError(
                message="Aliyun SMS SDK is not installed.",
                detail=str(_SMS_IMPORT_ERROR),
            )

        missing = [
            name
            for name, value in [
                ("SMS_ACCESS_KEY_ID", self._access_key_id),
                ("SMS_ACCESS_KEY_SECRET", self._access_key_secret),
                ("SMS_SIGN_NAME", self._sign_name),
                ("SMS_TEMPLATE_CODE", self._template_code),
            ]
            if not value
        ]
        if missing:
            raise SmsSendFailedError(
                message="Aliyun SMS configuration is incomplete.",
                detail=f"Missing: {', '.join(missing)}",
            )

    def _build_client(self) -> DysmsClient:
        global _shared_dysms_client
        if _shared_dysms_client is not None:
            return _shared_dysms_client

        config = open_api_models.Config(
            access_key_id=self._access_key_id,
            access_key_secret=self._access_key_secret,
            region_id=self._region,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        _shared_dysms_client = DysmsClient(config)
        return _shared_dysms_client

    async def send_login_code(self, phone: str, code: str) -> None:
        """Send a login verification code via Aliyun SMS."""

        client = self._client or self._build_client()
        request = dysms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=self._sign_name,
            template_code=self._template_code,
            template_param=json.dumps({"code": code}),
        )
        runtime = util_models.RuntimeOptions()

        try:
            response = await client.send_sms_with_options_async(request, runtime)
        except Exception as exc:  # pragma: no cover - external SDK errors are wrapped
            logger.error(f"Failed to send SMS via Aliyun: {exc}")
            raise SmsSendFailedError(message="Failed to send SMS.") from exc

        response_body = getattr(response, "body", None)
        response_code = getattr(response_body, "code", None)
        if response_code != "OK":
            logger.error(
                f"Aliyun SMS send returned non-OK code: {response_code}, message={getattr(response_body, 'message', None)}"
            )
            raise SmsSendFailedError(message="SMS provider returned an error.")

        logger.debug(f"Aliyun SMS sent successfully for phone ending with {phone[-4:]}")
