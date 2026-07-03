"""飞书 API 相关异常。"""

from __future__ import annotations

from typing import Any


class FeishuError(Exception):
    """飞书集成基础异常。"""


class FeishuConfigError(FeishuError):
    """飞书配置异常。"""


class FeishuAPIError(FeishuError):
    """飞书接口调用异常。"""

    def __init__(self, code: int | str, msg: str, response: dict[str, Any] | None = None):
        self.code = code
        self.msg = msg
        self.response = response
        super().__init__(f"飞书接口错误 code={code}, msg={msg}")
