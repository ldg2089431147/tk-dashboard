"""窗口配置读写 —— 支持多飞书接口存储。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "feishu_csv_updater_config.json"

DEFAULT_INTERFACE: dict[str, str] = {
    "name": "",
    "app_id": "",
    "app_secret": "",
    "app_token": "",
    "table_id": "tblRWlmlvudYAruS",
    "status": "未测试",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "interfaces": [],
    "last_used_index": -1,
    "rules_path": "",
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            path = Path.home() / "Library" / "Application Support" / "feishu-csv-updater"
        else:
            path = Path.home() / "AppData" / "Roaming" / "feishu-csv-updater"
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path.cwd()


def config_path() -> Path:
    return app_dir() / CONFIG_FILENAME


def load_window_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        save_window_config(DEFAULT_CONFIG)
        return _copy_default()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}

    result = _copy_default()
    if isinstance(data.get("interfaces"), list):
        clean: list[dict[str, str]] = []
        for item in data["interfaces"]:
            if isinstance(item, dict):
                entry = DEFAULT_INTERFACE.copy()
                for key in entry:
                    val = item.get(key)
                    entry[key] = str(val) if val is not None else ""
                clean.append(entry)
        result["interfaces"] = clean
    if isinstance(data.get("last_used_index"), (int, float)):
        result["last_used_index"] = int(data["last_used_index"])
    if isinstance(data.get("rules_path"), str):
        result["rules_path"] = data["rules_path"]
    return result


def save_window_config(config: dict[str, Any]) -> None:
    path = config_path()
    output: dict[str, Any] = {
        "interfaces": [],
        "last_used_index": -1,
        "rules_path": "",
    }
    if isinstance(config.get("interfaces"), list):
        for item in config["interfaces"]:
            if isinstance(item, dict):
                entry: dict[str, Any] = {}
                for key in DEFAULT_INTERFACE:
                    entry[key] = str(item.get(key, "")) if item.get(key) is not None else ""
                output["interfaces"].append(entry)
    if isinstance(config.get("last_used_index"), (int, float)):
        output["last_used_index"] = int(config["last_used_index"])
    if isinstance(config.get("rules_path"), str):
        output["rules_path"] = config["rules_path"]
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


def _copy_default() -> dict[str, Any]:
    return {
        "interfaces": [],
        "last_used_index": -1,
        "rules_path": "",
    }
