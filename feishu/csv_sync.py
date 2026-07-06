"""CSV 更新飞书寄样表。"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .bitable import BitableService


@dataclass
class CsvSyncConfig:
    app_token: str
    table_id: str
    csv_path: Path
    rules_path: Path
    timezone: str = "Asia/Shanghai"
    page_size: int = 500
    request_interval_seconds: float = 0.01


@dataclass
class CsvSyncResult:
    csv_rows: int = 0
    matched_records: int = 0
    planned_updates: int = 0
    updated: int = 0
    dry_run: bool = True
    field_changes: Counter[str] = field(default_factory=Counter)
    status_changes: Counter[str] = field(default_factory=Counter)
    status_skipped_by_protection: int = 0
    unknown_statuses: Counter[str] = field(default_factory=Counter)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "csv_rows": self.csv_rows,
            "matched_records": self.matched_records,
            "planned_updates": self.planned_updates,
            "updated": self.updated,
            "dry_run": self.dry_run,
            "field_changes": dict(self.field_changes),
            "status_changes": dict(self.status_changes),
            "status_skipped_by_protection": self.status_skipped_by_protection,
            "unknown_statuses": dict(self.unknown_statuses),
            "errors": self.errors,
        }


def default_rules_path() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller 内嵌文件在临时解压目录 _MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = Path(meipass) / "feishu_csv_update_rules.json"
            if bundled.exists():
                return bundled
    return Path.cwd() / "feishu_csv_update_rules.json"


def load_rules(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_connection(service: BitableService, app_token: str, table_id: str) -> int | None:
    payload = service.list_records(app_token, table_id, page_size=1)
    data = payload.get("data") or {}
    total = data.get("total")
    return int(total) if isinstance(total, int) else None


def sync_csv_to_bitable(
    service: BitableService,
    config: CsvSyncConfig,
    *,
    dry_run: bool = True,
    progress: Callable[[str], None] | None = None,
) -> CsvSyncResult:
    rules = load_rules(config.rules_path)
    csv_by_order = read_csv_by_order(config.csv_path)
    status_lookup = build_status_lookup(rules)
    result = CsvSyncResult(dry_run=dry_run)
    result.csv_rows = len(csv_by_order)

    for row in csv_by_order.values():
        raw_status = (row.get("Order Substatus") or "").strip()
        if raw_status and raw_status not in status_lookup:
            result.unknown_statuses[raw_status] += 1

    if result.unknown_statuses:
        return result

    updates = build_updates(service, config, rules, csv_by_order, status_lookup, result)
    result.planned_updates = len(updates)

    if dry_run:
        result.updated = len(updates)
        return result

    batch_size = 500
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        batch_records = [
            {"record_id": rid, "fields": payload}
            for rid, payload in batch
        ]
        try:
            service.batch_update_records(config.app_token, config.table_id, batch_records)
            result.updated += len(batch)
            if progress:
                progress(f"已更新 {result.updated}/{len(updates)}", result.updated, len(updates))
        except Exception as exc:
            for rid, _payload in batch:
                result.errors.append((rid, str(exc)))
            if progress:
                progress(f"批量更新失败：{exc}", result.updated, len(updates))
        if i + batch_size < len(updates):
            time.sleep(config.request_interval_seconds)

    return result


def build_updates(
    service: BitableService,
    config: CsvSyncConfig,
    rules: dict[str, Any],
    csv_by_order: dict[str, dict[str, str]],
    status_lookup: dict[str, str],
    result: CsvSyncResult,
) -> list[tuple[str, dict[str, Any]]]:
    allowed = set(rules["update_scope"]["allowed_target_fields"])
    csv_source_fields = set(rules["update_scope"].get("csv_source_of_truth_fields", []))
    overwritable = set(rules["sign_status_update_rules"]["protect_existing_status"]["overwritable_statuses"])
    today_ms = today_midnight_ms(config.timezone)
    field_names = list(allowed | {"视频链接"})
    updates: list[tuple[str, dict[str, Any]]] = []

    for record in service.iter_all_records(
        config.app_token,
        config.table_id,
        page_size=config.page_size,
        field_names=field_names,
    ):
        fields = record.get("fields") or {}
        row = csv_by_order.get(normalize(fields.get("订单ID")))
        if not row:
            continue

        result.matched_records += 1
        payload: dict[str, Any] = {}

        for csv_field, target_field in rules["field_mapping"].items():
            if target_field not in allowed or target_field == "签收状态" or target_field not in csv_source_fields:
                continue
            if target_field == "签收日期":
                csv_text = date_only_text(row.get(csv_field) or "")
                current_text = date_field_to_text(fields.get(target_field))
                if current_text != csv_text:
                    payload[target_field] = date_text_to_field(csv_text)
                continue

            value = (row.get(csv_field) or "").strip()
            if normalize(fields.get(target_field)) != value:
                payload[target_field] = value

        raw_status = (row.get("Order Substatus") or "").strip()
        mapped_status = status_lookup.get(raw_status)
        if mapped_status:
            current_status = normalize(fields.get("签收状态"))
            video_link = normalize(fields.get("视频链接"))
            desired_status = "已发布" if video_link else mapped_status
            can_update_status = bool(video_link) or (not current_status) or current_status in overwritable
            if can_update_status:
                if current_status != desired_status:
                    payload["签收状态"] = desired_status
                    payload["查询日期"] = today_ms
                    result.status_changes[desired_status] += 1
            elif current_status != desired_status:
                result.status_skipped_by_protection += 1

        payload = {key: value for key, value in payload.items() if key in allowed}
        if payload:
            record_id = record.get("record_id") or record.get("id")
            if not record_id:
                result.errors.append(("<unknown>", "记录缺少 record_id"))
                continue
            updates.append((record_id, payload))
            for field_name in payload:
                result.field_changes[field_name] += 1

    return updates


def read_csv_by_order(csv_path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    text = read_text_with_fallback(csv_path)
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        order_id = (row.get("Order ID") or "").strip()
        if order_id:
            rows[order_id] = row
    return rows


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def build_status_lookup(rules: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for target, sources in rules["sign_status_mapping"].items():
        for source in sources:
            lookup[source.strip()] = target
    return lookup


def normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_date_mdy(text: str) -> str:
    """解析 MM/DD/YYYY 格式，返回 YYYY-MM-DD 或空字符串"""
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        m, d, y = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return ""

def date_only_text(value: str) -> str:
    value = value.strip()
    # 先尝试 YYYY-MM-DD
    match = re.search(r"\d{4}-\d{1,2}-\d{1,2}", value)
    if match:
        year, month, day = match.group(0).split("-")
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    # 再尝试 MM/DD/YYYY（CSV常见格式）
    return _parse_date_mdy(value)


def date_text_to_field(value: str) -> int | None:
    if not value:
        return None
    parsed = dt.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1000)


def date_field_to_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return dt.datetime.fromtimestamp(int(value) / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return str(value).strip()


def today_midnight_ms(timezone: str) -> int:
    try:
        from zoneinfo import ZoneInfo

        tzinfo = ZoneInfo(timezone)
    except Exception:  # noqa: BLE001
        tzinfo = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
    now = dt.datetime.now(tzinfo)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 1000)
