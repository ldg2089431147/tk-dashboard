"""飞书 tenant_access_token 获取与缓存。"""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

from .config import FeishuConfig
from .exceptions import FeishuAPIError


class TenantTokenProvider:
    """获取并缓存 tenant_access_token。"""

    def __init__(
        self,
        config: FeishuConfig,
        session: requests.Session | None = None,
        timeout: float = 10,
        refresh_margin_seconds: int = 120,
    ):
        self.config = config
        self.session = session or requests.Session()
        self.timeout = timeout
        self.refresh_margin_seconds = refresh_margin_seconds
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        """返回可用 token，必要时自动刷新。"""
        if self._is_token_valid():
            return self._token or ""

        with self._lock:
            if self._is_token_valid():
                return self._token or ""
            self._refresh_token()
            return self._token or ""

    def _is_token_valid(self) -> bool:
        return bool(self._token) and time.time() < self._expires_at - self.refresh_margin_seconds

    def _refresh_token(self) -> None:
        url = f"{self.config.base_url}/auth/v3/tenant_access_token/internal"
        response = self.session.post(
            url,
            json={"app_id": self.config.app_id, "app_secret": self.config.app_secret},
            timeout=self.timeout,
        )
        payload = self._parse_response(response)
        token = payload.get("tenant_access_token")
        expire = payload.get("expire", 0)

        if not token:
            raise FeishuAPIError(payload.get("code", "missing_token"), "响应中缺少 tenant_access_token", payload)

        self._token = token
        self._expires_at = time.time() + int(expire)

    @staticmethod
    def _parse_response(response: requests.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
            payload = response.json()
        except requests.HTTPError as exc:
            raise FeishuAPIError(response.status_code, response.text) from exc
        except ValueError as exc:
            raise FeishuAPIError("invalid_json", "飞书接口返回了非 JSON 响应") from exc

        if payload.get("code") != 0:
            raise FeishuAPIError(payload.get("code", "unknown"), payload.get("msg", "未知错误"), payload)
        return payload
