"""寄样表签收状态同步规则。"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .bitable import BitableService

FIELD_VIDEO = "视频链接"
FIELD_STATUS = "签收状态"
FIELD_SIGN_DATE = "签收日期"
FIELD_QUERY_DATE = "查询日期"

STATUS_TRANSIT = "运输中"
STATUS_SIGNED = "已签收"
STATUS_PUBLISHED = "已发布"


@dataclass
class SyncDetail:
    """单条记录同步详情。"""

    record_id: str
    fields: dict[str, Any]


@dataclass
class SyncResult:
    """寄样表同步结果。"""

    total: int = 0
    matched: int = 0
    updated: int = 0
    dry_run: bool = True
    details: list[SyncDetail] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)


def today_local_midnight_ms(timezone: str = "Asia/Shanghai") -> int:
    """返回指定时区当天 00:00:00 的毫秒时间戳。"""
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        if timezone not in {"Asia/Shanghai", "Asia/Chongqing", "Asia/Harbin"}:
            raise
        tz = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
    now = dt.datetime.now(tz)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 1000)


def is_empty_value(value: Any) -> bool:
    """判断飞书字段值是否为空。"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def normalize_status(value: Any) -> str | None:
    """把飞书单选/文本状态字段归一化为字符串。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "name", "value"):
            text = value.get(key)
            if isinstance(text, str):
                return text
        return None
    if isinstance(value, list) and value:
        return normalize_status(value[0])
    return str(value)


def add_changed_field(updates: dict[str, Any], current_fields: dict[str, Any], field_name: str, value: Any) -> None:
    """仅当目标值和当前值不一致时加入更新字段。"""
    if current_fields.get(field_name) != value:
        updates[field_name] = value


def build_sample_table_updates(record: dict[str, Any], today_ms: int) -> dict[str, Any]:
    """根据寄样表规则生成单条记录需要更新的字段。"""
    fields = record.get("fields") or {}
    updates: dict[str, Any] = {}

    video = fields.get(FIELD_VIDEO)
    sign_date = fields.get(FIELD_SIGN_DATE)
    current_status = normalize_status(fields.get(FIELD_STATUS))

    if not is_empty_value(video) and current_status != STATUS_PUBLISHED:
        updates[FIELD_STATUS] = STATUS_PUBLISHED
        add_changed_field(updates, fields, FIELD_SIGN_DATE, today_ms)
    elif is_empty_value(video) and not is_empty_value(sign_date) and current_status != STATUS_SIGNED:
        updates[FIELD_STATUS] = STATUS_SIGNED
        add_changed_field(updates, fields, FIELD_SIGN_DATE, today_ms)

    if current_status == STATUS_TRANSIT:
        add_changed_field(updates, fields, FIELD_QUERY_DATE, today_ms)

    return updates


def sync_sample_table(
    service: BitableService,
    app_token: str,
    table_id: str,
    *,
    dry_run: bool = True,
    page_size: int = 500,
    timezone: str = "Asia/Shanghai",
) -> SyncResult:
    """遍历寄样表，并按规则同步签收状态。"""
    today_ms = today_local_midnight_ms(timezone)
    result = SyncResult(dry_run=dry_run)

    for record in service.iter_all_records(app_token, table_id, page_size=page_size):
        result.total += 1
        record_id = record.get("record_id") or record.get("id")
        if not record_id:
            result.errors.append(("<unknown>", "记录缺少 record_id"))
            continue

        updates = build_sample_table_updates(record, today_ms)
        if not updates:
            continue

        result.matched += 1
        result.details.append(SyncDetail(record_id=record_id, fields=updates))

        if dry_run:
            continue

        try:
            service.update_record(app_token, table_id, record_id, updates)
            result.updated += 1
        except Exception as exc:  # noqa: BLE001 - 需要汇总单条记录失败原因并继续处理后续记录
            result.errors.append((record_id, str(exc)))

    if dry_run:
        result.updated = result.matched

    return result
