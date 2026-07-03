"""飞书多维表格命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv

from .bitable import BitableService
from .client import FeishuClient
from .config import load_config
from .exceptions import FeishuError


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="飞书多维表格 API CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_tables = subparsers.add_parser("list-tables", help="列出多维表格中的数据表")
    add_app_args(list_tables)
    list_tables.add_argument("--page-size", type=int, default=100)
    list_tables.add_argument("--page-token")

    list_records = subparsers.add_parser("list-records", help="列出数据表记录")
    add_app_args(list_records)
    add_table_args(list_records)
    list_records.add_argument("--page-size", type=int, default=100)
    list_records.add_argument("--page-token")
    list_records.add_argument("--view-id")
    list_records.add_argument("--field-names", help="JSON 数组，例如：[\"名称\",\"数量\"]")
    list_records.add_argument("--filter", dest="filter_", help="飞书多维表格 filter 参数")
    list_records.add_argument("--sort", help="JSON 数组形式的排序参数")

    create_record = subparsers.add_parser("create-record", help="创建一条数据表记录")
    add_app_args(create_record)
    add_table_args(create_record)
    create_record.add_argument("--fields-json", required=True, help="字段 JSON 对象，例如：'{\"名称\":\"测试\"}'")

    sync_sample_table = subparsers.add_parser("sync-sample-table", help="按规则同步寄样表签收状态")
    add_app_args(sync_sample_table)
    add_table_args(sync_sample_table)
    sync_sample_table.add_argument("--dry-run", action="store_true", help="预览模式，不修改飞书数据")
    sync_sample_table.add_argument("--apply", action="store_true", help="真实执行更新")
    sync_sample_table.add_argument("--page-size", type=int, default=500)
    sync_sample_table.add_argument("--timezone", default="Asia/Shanghai")

    return parser


def add_app_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--app-token", help="多维表格 app_token；未传时读取 FEISHU_APP_TOKEN")


def add_table_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--table-id", help="多维表格 table_id；未传时读取 FEISHU_TABLE_ID")


def get_app_token(args: argparse.Namespace) -> str:
    app_token = args.app_token or os.getenv("FEISHU_APP_TOKEN")
    if not app_token:
        raise ValueError("缺少 app_token，请传入 --app-token 或设置 FEISHU_APP_TOKEN")
    return app_token


def get_table_id(args: argparse.Namespace) -> str:
    table_id = args.table_id or os.getenv("FEISHU_TABLE_ID")
    if not table_id:
        raise ValueError("缺少 table_id，请传入 --table-id 或设置 FEISHU_TABLE_ID")
    return table_id


def parse_json_object(raw: str, name: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{name} 必须是 JSON 对象")
    return value


def parse_json_list(raw: str | None, name: str) -> list[Any] | None:
    if not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"{name} 必须是 JSON 数组")
    return value


def print_sync_result(result: Any) -> None:
    """打印寄样表同步结果。"""
    mode = "预览" if result.dry_run else "执行"
    print(f"{mode}完成")
    print(f"扫描记录数：{result.total}")
    print(f"待更新记录数：{result.matched}")
    print(f"{'预计更新记录数' if result.dry_run else '成功更新记录数'}：{result.updated}")
    print(f"错误数：{len(result.errors)}")

    if result.details:
        print("\n更新详情：")
        for detail in result.details:
            fields_json = json.dumps(detail.fields, ensure_ascii=False)
            print(f"- {detail.record_id}: {fields_json}")

    if result.errors:
        print("\n错误详情：", file=sys.stderr)
        for record_id, message in result.errors:
            print(f"- {record_id}: {message}", file=sys.stderr)


def main() -> int:
    """CLI 主入口。"""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = load_config()
        service = BitableService(FeishuClient(config))
        app_token = get_app_token(args)

        if args.command == "list-tables":
            result = service.list_tables(app_token, page_size=args.page_size, page_token=args.page_token)
        elif args.command == "list-records":
            result = service.list_records(
                app_token,
                get_table_id(args),
                page_size=args.page_size,
                page_token=args.page_token,
                view_id=args.view_id,
                field_names=parse_json_list(args.field_names, "--field-names"),
                filter_=args.filter_,
                sort=parse_json_list(args.sort, "--sort"),
            )
        elif args.command == "create-record":
            result = service.create_record(app_token, get_table_id(args), parse_json_object(args.fields_json, "--fields-json"))
        elif args.command == "sync-sample-table":
            if args.dry_run and args.apply:
                raise ValueError("--dry-run 和 --apply 不能同时使用")
            from .sample_table import sync_sample_table

            result = sync_sample_table(
                service,
                app_token,
                get_table_id(args),
                dry_run=not args.apply,
                page_size=args.page_size,
                timezone=args.timezone,
            )
            print_sync_result(result)
            return 0 if not result.errors else 1
        else:
            parser.error(f"未知命令：{args.command}")
            return 2

        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (FeishuError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
