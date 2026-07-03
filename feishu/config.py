"""飞书配置读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .exceptions import FeishuConfigError


@dataclass(frozen=True)
class FeishuConfig:
    """飞书开放平台配置。"""

    app_id: str
    app_secret: str
    base_url: str = "https://open.feishu.cn/open-apis"


def load_config() -> FeishuConfig:
    """从环境变量读取飞书配置。"""
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    base_url = os.getenv("FEISHU_BASE_URL", FeishuConfig.base_url)

    if not app_id:
        raise FeishuConfigError("缺少环境变量 FEISHU_APP_ID")
    if not app_secret:
        raise FeishuConfigError("缺少环境变量 FEISHU_APP_SECRET")

    return FeishuConfig(app_id=app_id, app_secret=app_secret, base_url=base_url.rstrip("/"))
