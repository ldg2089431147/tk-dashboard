"""TikTok Shop API 封装"""
import requests
import time
from config import Config


class TikTokShopAPI:
    def __init__(self):
        self.app_key = Config.APP_KEY
        self.app_secret = Config.APP_SECRET
        self.shop_id = Config.SHOP_ID
        self.access_token = Config.ACCESS_TOKEN
        self.refresh_token = Config.REFRESH_TOKEN
        self.base_url = Config.API_BASE

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "x-tts-access-token": self.access_token,
        }

    def _request(self, method, path, params=None, data=None):
        url = f"{self.base_url}{path}"
        headers = self._headers()
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=10)
            else:
                resp = requests.post(url, headers=headers, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e), "code": -1}

    # ── 订单 ──
    def get_orders(self, days=7, page_size=20, page=1):
        """获取最近 N 天的订单"""
        now = int(time.time())
        create_from = now - days * 86400
        params = {
            "create_time_from": create_from,
            "create_time_to": now,
            "page_size": page_size,
            "page": page,
        }
        return self._request("GET", "/order/202309/orders", params=params)

    def get_order_detail(self, order_id):
        """获取订单详情"""
        return self._request("GET", f"/order/202309/orders/{order_id}")

    # ── 商品 ──
    def get_products(self, page_size=20, page=1):
        """获取商品列表"""
        params = {"page_size": page_size, "page": page}
        return self._request("GET", "/product/202309/products", params=params)

    # ── 数据 ──
    def get_shop_stats(self, date_str):
        """获取指定日期的店铺数据"""
        params = {"date": date_str}
        return self._request("GET", "/analytics/202309/shop_data", params=params)
