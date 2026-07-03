# TikTok Shop API 配置
# 在 Railway 上用环境变量，不要硬编码

import os

class Config:
    APP_KEY = os.getenv("TK_APP_KEY", "")
    APP_SECRET = os.getenv("TK_APP_SECRET", "")
    SHOP_ID = os.getenv("TK_SHOP_ID", "")
    ACCESS_TOKEN = os.getenv("TK_ACCESS_TOKEN", "")
    REFRESH_TOKEN = os.getenv("TK_REFRESH_TOKEN", "")
    
    # API 基础地址（根据你的店铺区域选择）
    # 美区: https://open-api.tiktokshop.com
    # 东南亚: https://open-api.tiktokshop.com
    API_BASE = "https://open-api.tiktokshop.com"
