"""飞书开放平台 HTTP 客户端。"""

from __future__ import annotations

from typing import Any

import requests

from .auth import TenantTokenProvider
from .config import FeishuConfig
from .exceptions import FeishuAPIError


class FeishuClient:
    """统一处理飞书开放平台请求。"""

    def __init__(
        self,
        config: FeishuConfig,
        token_provider: TenantTokenProvider | None = None,
        session: requests.Session | None = None,
        timeout: float = 10,
    ):
        self.config = config
        self.session = session or requests.Session()
        self.timeout = timeout
        self.token_provider = token_provider or TenantTokenProvider(config, session=self.session, timeout=timeout)

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """发送飞书开放平台请求并检查业务错误。"""
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        headers = kwargs.pop("headers", {}) or {}
        headers.update(
            {
                "Authorization": f"Bearer {self.token_provider.get_token()}",
                "Content-Type": "application/json; charset=utf-8",
            }
        )

        response = self.session.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        return self._parse_response(response)

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """发送 GET 请求。"""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """发送 POST 请求。"""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """发送 PUT 请求。"""
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """发送 PATCH 请求。"""
        return self.request("PATCH", path, **kwargs)

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
