"""飞书多维表格 API 封装。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from .client import FeishuClient


class BitableService:
    """多维表格常用接口。"""

    def __init__(self, client: FeishuClient):
        self.client = client

    def list_tables(
        self,
        app_token: str,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """列出多维表格中的数据表。"""
        params: dict[str, Any] = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token

        return self.client.get(f"/bitable/v1/apps/{app_token}/tables", params=params)

    def list_records(
        self,
        app_token: str,
        table_id: str,
        page_size: int = 100,
        page_token: str | None = None,
        view_id: str | None = None,
        field_names: list[str] | None = None,
        filter_: str | None = None,
        sort: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """列出指定数据表中的记录。"""
        params: dict[str, Any] = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        if view_id:
            params["view_id"] = view_id
        if field_names:
            params["field_names"] = json.dumps(field_names, ensure_ascii=False)
        if filter_:
            params["filter"] = filter_
        if sort:
            params["sort"] = json.dumps(sort, ensure_ascii=False)

        return self.client.get(f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", params=params)

    def create_record(self, app_token: str, table_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """创建一条多维表格记录。"""
        return self.client.post(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            json={"fields": fields},
        )

    def update_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """更新一条多维表格记录。"""
        return self.client.put(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            json={"fields": fields},
        )

    def batch_update_records(
        self,
        app_token: str,
        table_id: str,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量更新多维表格记录，单次最多 500 条。"""
        return self.client.post(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            json={"records": records},
        )

    def iter_all_records(
        self,
        app_token: str,
        table_id: str,
        page_size: int = 500,
        view_id: str | None = None,
        field_names: list[str] | None = None,
        filter_: str | None = None,
        sort: list[dict[str, Any]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """自动翻页遍历所有记录。"""
        page_token: str | None = None
        while True:
            payload = self.list_records(
                app_token,
                table_id,
                page_size=page_size,
                page_token=page_token,
                view_id=view_id,
                field_names=field_names,
                filter_=filter_,
                sort=sort,
            )
            data = payload.get("data") or {}
            yield from data.get("items") or []

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
