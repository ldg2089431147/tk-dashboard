"""飞书寄样表更新工具 —— 窗口应用。"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from .bitable import BitableService
from .client import FeishuClient
from .config import FeishuConfig
from .csv_sync import (
    CsvSyncConfig,
    CsvSyncResult,
    default_rules_path,
    load_rules,
    sync_csv_to_bitable,
    test_connection,
)
from .gui_config import DEFAULT_INTERFACE, config_path, load_window_config, save_window_config

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES

    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False


def _font(size: int, weight: str = "") -> tuple[str, int, str]:
    family = "PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei UI"
    return (family, size, weight)


def _bold_font(size: int) -> tuple[str, int, str]:
    return _font(size, "bold")


class CsvUpdaterApp(TkinterDnD.Tk if _DND_AVAILABLE else tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("飞书寄样表更新工具")
        self.geometry("1040x760")
        self.minsize(1040, 760)
        self.log_queue: queue.Queue[str] = queue.Queue()

        saved = load_window_config()
        self.interfaces: list[dict[str, str]] = saved["interfaces"]
        self.selected_interface: dict[str, str] | None = None
        self.csv_paths: list[str] = []
        self.csv_path = tk.StringVar()
        self.preview_stat_values: dict[str, ttk.Label] = {}
        self.status_var = tk.StringVar(value="请选择飞书接口")
        self._saved_status = "请选择飞书接口"
        self._spinning = False
        self._spinner_chars = "◐◓◑◒"
        self._spinner_idx = 0
        self.preview_result_data: dict[str, Any] = {}

        self.content = ttk.Frame(self)
        self._build_shell()
        self.after(10, self._load_last_or_show_list)
        self.after(100, self._drain_log_queue)

    # ── 外壳 ────────────────────────────────────────

    def _build_shell(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        header = ttk.Frame(self, padding=(22, 10, 22, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="飞书寄样表更新工具", font=_bold_font(20)).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.status_var, foreground="#555555").grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.content = ttk.Frame(self, padding=(22, 2, 22, 2))
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        # 底部固定按钮栏
        self.action_bar = ttk.Frame(self, padding=(22, 8, 22, 16))
        self.action_bar.grid(row=2, column=0, sticky="ew")
        self.action_bar.columnconfigure(0, weight=1)
        self.action_bar.columnconfigure(1, weight=1)

        self.spinner_label = ttk.Label(
            self, text="", font=_bold_font(18),
            foreground="red", anchor="center",
        )

    def clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _clear_action_bar(self) -> None:
        for child in self.action_bar.winfo_children():
            child.destroy()

    def _set_action_buttons(self, left: tuple[str, Callable] | None = None, right: tuple[str, Callable] | None = None, right2: tuple[str, Callable] | None = None) -> None:
        self._clear_action_bar()
        if left:
            ttk.Button(self.action_bar, text=left[0], command=left[1]).pack(side="left")
        if right:
            ttk.Button(self.action_bar, text=right[0], command=right[1]).pack(side="right")
        if right2:
            ttk.Button(self.action_bar, text=right2[0], command=right2[1]).pack(side="right", padx=(0, 8))

    # ── 第 1 步：选择接口 ──────────────────────────

    def _load_last_or_show_list(self) -> None:
        last_idx = load_window_config().get("last_used_index", -1)
        if isinstance(last_idx, int) and 0 <= last_idx < len(self.interfaces):
            self.selected_interface = self.interfaces[last_idx]
            self.show_upload_csv()
        else:
            self.show_select_interface()

    def show_select_interface(self) -> None:
        self.clear_content()
        self.set_status("请选择飞书接口")
        self._set_action_buttons(
            right=("下一步：上传 CSV 文件", self.go_upload_from_select),
        )
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=3)
        page.columnconfigure(1, weight=2, minsize=300)
        page.rowconfigure(1, weight=1)

        title = ttk.Frame(page)
        title.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(title, text="第 1 步：选择飞书接口", font=_bold_font(16)).pack(anchor="w")
        ttk.Label(title, text="选择已有接口，或者新建一个飞书接口。", foreground="#666666").pack(anchor="w", pady=(6, 0))

        list_box = ttk.LabelFrame(page, text="已保存接口", padding=14)
        list_box.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        list_box.columnconfigure(0, weight=1)
        list_box.rowconfigure(1, weight=1)

        self.interface_table = ttk.Treeview(list_box, columns=("name", "table", "status"), show="headings", height=10)
        self.interface_table.heading("name", text="接口名称")
        self.interface_table.heading("table", text="Table ID")
        self.interface_table.heading("status", text="状态")
        self.interface_table.column("name", width=240)
        self.interface_table.column("table", width=180)
        self.interface_table.column("status", width=80, anchor="center")
        self.interface_table.grid(row=1, column=0, sticky="nsew")
        self.interface_table.bind("<Double-1>", lambda _event: self.use_selected_interface())
        self.interface_table.bind("<Button-3>", self.show_interface_context_menu)
        self.interface_menu = tk.Menu(self, tearoff=0)
        self.interface_menu.add_command(label="测试选中接口", command=self.test_selected_interface)
        self.interface_menu.add_command(label="编辑选中接口", command=self.edit_selected_interface)
        self.interface_menu.add_command(label="删除选中接口", command=self.delete_selected_interface)
        self._refresh_interface_table()

        side = ttk.Frame(page)
        side.grid(row=1, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        action_box = ttk.LabelFrame(side, text="接口操作", padding=16)
        action_box.grid(row=0, column=0, sticky="ew")
        ttk.Label(action_box, text="双击左侧接口即可使用；也可以先选中后测试、编辑或删除。", wraplength=280, foreground="#555555").pack(anchor="w")
        ttk.Button(action_box, text="测试选中接口", command=self.test_selected_interface).pack(fill="x", pady=(14, 8))
        ttk.Button(action_box, text="编辑选中接口", command=self.edit_selected_interface).pack(fill="x", pady=(0, 8))
        ttk.Button(action_box, text="删除选中接口", command=self.delete_selected_interface).pack(fill="x")

        new_box = ttk.LabelFrame(side, text="没有接口？", padding=16)
        new_box.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(new_box, text="新建一个飞书接口后，下次打开会出现在左侧列表里。", wraplength=280, foreground="#555555").pack(anchor="w")
        ttk.Button(new_box, text="新建飞书接口", command=self.show_create_interface).pack(fill="x", pady=(16, 0))

        detail_box = ttk.LabelFrame(side, text="下一步", padding=16)
        detail_box.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(detail_box, text="选择接口后，进入上传 CSV 文件。", wraplength=280).pack(anchor="w")

    def _refresh_interface_table(self) -> None:
        if not hasattr(self, "interface_table"):
            return
        for item in self.interface_table.get_children():
            self.interface_table.delete(item)
        for item in self.interfaces:
            self.interface_table.insert("", "end", values=(item["name"], item["table_id"], item["status"]))

    def use_selected_interface(self) -> None:
        selected = self.interface_table.selection()
        if not selected:
            messagebox.showwarning("请选择接口", "请先在左侧列表中选择一个飞书接口。")
            return
        index = self.interface_table.index(selected[0])
        self.selected_interface = self.interfaces[index]
        self._save_last_used(index)
        self.show_upload_csv()

    def show_interface_context_menu(self, event: tk.Event) -> None:
        item = self.interface_table.identify_row(event.y)
        if item:
            self.interface_table.selection_set(item)
            self.interface_menu.tk_popup(event.x_root, event.y_root)

    def _get_selected_interface_index(self) -> int | None:
        selected = self.interface_table.selection()
        if not selected:
            return None
        idx = self.interface_table.index(selected[0])
        return idx if 0 <= idx < len(self.interfaces) else None

    def test_selected_interface(self) -> None:
        idx = self._get_selected_interface_index()
        if idx is None:
            messagebox.showwarning("请选择接口", "请先选择接口，再测试连接。")
            return
        self._test_interface(self.interfaces[idx], index=idx)

    def edit_selected_interface(self) -> None:
        idx = self._get_selected_interface_index()
        if idx is None:
            messagebox.showwarning("请选择接口", "请先选择要编辑的接口。")
            return
        self.show_create_interface(edit_index=idx)

    def delete_selected_interface(self) -> None:
        selected = self.interface_table.selection()
        if not selected:
            messagebox.showwarning("请选择接口", "请先选择要删除的接口。")
            return
        if not messagebox.askyesno("确认删除", "确定删除选中的飞书接口吗？"):
            return
        idx = self.interface_table.index(selected[0])
        if 0 <= idx < len(self.interfaces):
            del self.interfaces[idx]
        self._persist_interfaces()
        self._refresh_interface_table()

    def go_upload_from_select(self) -> None:
        if not self.selected_interface:
            messagebox.showwarning("缺少接口", "请先选择一个飞书接口，或新建并使用。")
            return
        self.show_upload_csv()

    def _save_last_used(self, index: int) -> None:
        cfg = load_window_config()
        cfg["last_used_index"] = index
        save_window_config(cfg)

    def _persist_interfaces(self) -> None:
        cfg = load_window_config()
        cfg["interfaces"] = self.interfaces
        save_window_config(cfg)

    # ── 新建 / 编辑接口 ────────────────────────────

    def show_create_interface(self, edit_index: int | None = None) -> None:
        self.clear_content()
        is_edit = edit_index is not None
        self.set_status("编辑飞书接口" if is_edit else "新建飞书接口")
        self._edit_index = edit_index
        self._set_action_buttons(
            left=("返回接口选择", self.show_select_interface),
            right=("保存并使用", self.save_and_use_new_interface),
        )

        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)

        ttk.Label(page, text="编辑飞书接口" if is_edit else "新建飞书接口", font=_bold_font(16)).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="填写飞书应用和多维表格信息，保存后回到接口选择。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        form = ttk.LabelFrame(page, text="接口信息", padding=18)
        form.grid(row=2, column=0, sticky="new")
        form.columnconfigure(1, weight=1)

        self.name_var = tk.StringVar()
        self.app_id_var = tk.StringVar()
        self.app_secret_var = tk.StringVar()
        self.app_token_var = tk.StringVar()
        self.table_id_var = tk.StringVar()
        self.interface_status_var = tk.StringVar(value="未测试")

        if is_edit:
            data = self.interfaces[edit_index]
            self.name_var.set(data["name"])
            self.app_id_var.set(data["app_id"])
            self.app_secret_var.set(data["app_secret"])
            self.app_token_var.set(data["app_token"])
            self.table_id_var.set(data["table_id"])
            self.interface_status_var.set(data.get("status", "未测试"))

        self._entry(form, 0, "接口名称", self.name_var)
        self._entry(form, 1, "App ID", self.app_id_var)
        self._entry(form, 2, "App Secret", self.app_secret_var, secret=True)
        self._entry(form, 3, "App Token", self.app_token_var)
        self._entry(form, 4, "Table ID", self.table_id_var)
        ttk.Label(form, text="接口状态").grid(row=5, column=0, sticky="w", pady=8)
        ttk.Label(form, textvariable=self.interface_status_var).grid(row=5, column=1, sticky="w", padx=(12, 0), pady=8)

        buttons = ttk.Frame(form)
        buttons.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        ttk.Button(buttons, text="测试连接", command=self.test_new_interface).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="保存接口", command=self.save_new_interface).pack(side="left")

        help_box = ttk.LabelFrame(page, text="填写说明", padding=14)
        help_box.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        for text in ["App ID / App Secret 来自飞书开放平台自建应用。", "App Token 是多维表格 app_token。", "Table ID 是寄样表的数据表 ID，通常以 tbl 开头。"]:
            ttk.Label(help_box, text=f"• {text}", foreground="#555555").pack(anchor="w", pady=2)

    def test_new_interface(self) -> None:
        if not self._validate_new_interface():
            return
        data = self._new_interface_data()
        data["status"] = self.interface_status_var.get()
        self.interface_status_var.set("测试中")

        def update_form_status(status: str) -> None:
            self.interface_status_var.set(status)

        self._test_interface(data, on_status=update_form_status)

    def save_new_interface(self) -> None:
        if not self._validate_new_interface():
            return
        data = self._new_interface_data()
        edit_idx = getattr(self, "_edit_index", None)
        if edit_idx is not None and 0 <= edit_idx < len(self.interfaces):
            self.interfaces[edit_idx] = data
        else:
            self.interfaces.append(data)
        self._persist_interfaces()
        messagebox.showinfo("保存成功", "飞书接口已保存。")
        self.show_select_interface()

    def save_and_use_new_interface(self) -> None:
        if not self._validate_new_interface():
            return
        data = self._new_interface_data()
        edit_idx = getattr(self, "_edit_index", None)
        if edit_idx is not None and 0 <= edit_idx < len(self.interfaces):
            self.interfaces[edit_idx] = data
        else:
            self.interfaces.append(data)
            edit_idx = len(self.interfaces) - 1
        self._persist_interfaces()
        self.selected_interface = data
        self._save_last_used(edit_idx)
        messagebox.showinfo("保存成功", "飞书接口已保存并选中。")
        self.show_upload_csv()

    def _validate_new_interface(self) -> bool:
        checks = [
            (self.name_var.get().strip(), "请输入接口名称"),
            (self.app_id_var.get().strip(), "请输入 App ID"),
            (self.app_secret_var.get().strip(), "请输入 App Secret"),
            (self.app_token_var.get().strip(), "请输入 App Token"),
            (self.table_id_var.get().strip(), "请输入 Table ID"),
        ]
        for value, msg in checks:
            if not value:
                messagebox.showwarning("信息不完整", msg)
                return False
        return True

    def _new_interface_data(self) -> dict[str, str]:
        return {
            "name": self.name_var.get().strip(),
            "app_id": self.app_id_var.get().strip(),
            "app_secret": self.app_secret_var.get().strip(),
            "app_token": self.app_token_var.get().strip(),
            "table_id": self.table_id_var.get().strip(),
            "status": self.interface_status_var.get().strip() or "未测试",
        }

    def _test_interface(
        self,
        data: dict[str, str],
        index: int | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        app_id = data["app_id"].strip()
        app_secret = data["app_secret"].strip()
        app_token = data["app_token"].strip()
        table_id = data["table_id"].strip()
        if not all([app_id, app_secret, app_token, table_id]):
            raise ValueError("飞书接口信息不完整，请检查。")

        if index is not None and 0 <= index < len(self.interfaces):
            self.interfaces[index]["status"] = "测试中"
            self._refresh_interface_table()
            self._persist_interfaces()

        if on_status:
            on_status("测试中")

        def mark_status(status: str) -> None:
            data["status"] = status
            if on_status:
                on_status(status)
            if index is not None and 0 <= index < len(self.interfaces):
                self.interfaces[index]["status"] = status
                self._persist_interfaces()
                self._refresh_interface_table()

        def worker() -> None:
            service = BitableService(FeishuClient(FeishuConfig(app_id=app_id, app_secret=app_secret), timeout=30))
            total = test_connection(service, app_token, table_id)
            msg = f"连接成功，寄样表记录总数：{total}" if total is not None else "连接成功，已读取到寄样表记录。"
            self.log(msg)
            self._test_result = msg
            self.after(0, lambda: mark_status("正常"))

        def on_ok() -> None:
            messagebox.showinfo("测试连接", self._test_result)

        def on_error(exc: Exception) -> None:
            mark_status("失败")
            messagebox.showerror("测试连接", str(exc))

        self._run_background("测试连接", worker, on_ok=on_ok, on_error=on_error)

    # ── 第 2 步：上传 CSV ───────────────────────────

    def show_upload_csv(self) -> None:
        self.clear_content()
        name = self.selected_interface["name"] if self.selected_interface else "未选择"
        self.set_status(f"当前接口：{name}")
        self._set_action_buttons(
            left=("上一步：选择接口", self.show_select_interface),
            right=("下一步：预览更新", self.go_preview),
        )
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)

        ttk.Label(page, text="第 2 步：上传 CSV 文件", font=_bold_font(16)).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="可以一次选择多个 TikTok Manage orders CSV 文件，三个店铺的 CSV 文件可同时上传。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        box = ttk.LabelFrame(page, text="CSV 文件", padding=18)
        box.grid(row=2, column=0, sticky="nsew")
        page.rowconfigure(2, weight=1)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)

        top = ttk.Frame(box)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(0, weight=1)
        self.csv_count_var = tk.StringVar(value=f"已选择 CSV 文件：{len(self.csv_paths)} 个")
        ttk.Label(top, textvariable=self.csv_count_var).grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="添加 CSV 文件", command=self.choose_csv).grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(top, text="清空列表", command=self.clear_csv_files).grid(row=0, column=2, sticky="e", padx=(8, 0))

        drop_hint = ttk.Label(
            box,
            text="三个店铺的 CSV 文件可同时上传\n可直接拖到此区域，或点击右上角添加 CSV 文件",
            anchor="center",
            justify="center",
            foreground="#333333",
            font=_font(13, "bold"),
        )
        drop_hint.grid(row=1, column=0, sticky="ew", pady=(4, 12), ipady=10)

        self.csv_table = ttk.Treeview(box, columns=("file",), show="headings", height=8)
        self.csv_table.heading("file", text="CSV 文件路径")
        self.csv_table.column("file", width=780)
        self.csv_table.grid(row=2, column=0, sticky="nsew")
        self.csv_table.bind("<Button-3>", self.show_csv_context_menu)
        if _DND_AVAILABLE:
            box.drop_target_register(DND_FILES)
            box.dnd_bind("<<Drop>>", self.on_csv_drop)
        self.csv_menu = tk.Menu(self, tearoff=0)
        self.csv_menu.add_command(label="删除选中 CSV 文件", command=self.delete_selected_csv_file)
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=self.csv_table.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.csv_table.configure(yscrollcommand=scrollbar.set)
        for path in self.csv_paths:
            self.csv_table.insert("", "end", values=(path,))

        hint = ttk.LabelFrame(page, text="说明", padding=12)
        hint.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(hint, text="规则文件不需要在这里选择，程序内部固定使用当前更新规则。多个 CSV 文件会合并后一起匹配订单 ID；选中文件后右键可单独删除。", foreground="#555555").pack(anchor="w")

    def choose_csv(self) -> None:
        paths = filedialog.askopenfilenames(title="选择一个或多个 CSV 文件", filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not paths:
            return
        self._add_csv_files(paths)

    def on_csv_drop(self, event) -> None:
        raw = event.data.strip()
        files = self.tk.splitlist(raw)
        csv_files = [f for f in files if f.lower().endswith(".csv")]
        if csv_files:
            self._add_csv_files(csv_files)
        else:
            messagebox.showwarning("未发现 CSV 文件", "请拖入 .csv 文件。")

    def _add_csv_files(self, paths: list[str]) -> None:
        for path in paths:
            path = str(Path(path))
            if not Path(path).is_file() or not path.lower().endswith(".csv"):
                continue
            if path not in self.csv_paths:
                self.csv_paths.append(path)
                self.csv_table.insert("", "end", values=(path,))
        self.csv_path.set(";".join(self.csv_paths))
        self.csv_count_var.set(f"已选择 CSV 文件：{len(self.csv_paths)} 个")

    def clear_csv_files(self) -> None:
        self.csv_paths.clear()
        self.csv_path.set("")
        for item in self.csv_table.get_children():
            self.csv_table.delete(item)
        self.csv_count_var.set("已选择 CSV 文件：0 个")

    def show_csv_context_menu(self, event: tk.Event) -> None:
        item = self.csv_table.identify_row(event.y)
        if item:
            self.csv_table.selection_set(item)
            self.csv_menu.tk_popup(event.x_root, event.y_root)

    def delete_selected_csv_file(self) -> None:
        selected = self.csv_table.selection()
        if not selected:
            messagebox.showwarning("请选择 CSV 文件", "请先选中要删除的 CSV 文件。")
            return
        for item in selected:
            values = self.csv_table.item(item, "values")
            if values:
                path = values[0]
                if path in self.csv_paths:
                    self.csv_paths.remove(path)
            self.csv_table.delete(item)
        self.csv_path.set(";".join(self.csv_paths))
        self.csv_count_var.set(f"已选择 CSV 文件：{len(self.csv_paths)} 个")

    def go_preview(self) -> None:
        if not self.csv_paths:
            messagebox.showwarning("缺少 CSV 文件", "请先上传至少一个 CSV 文件。")
            return
        self.show_preview()

    # ── 第 3 步：预览 ──────────────────────────────

    def show_preview(self) -> None:
        self.clear_content()
        self.set_status("预览更新内容")
        self._set_action_buttons(
            left=("上一步：上传 CSV 文件", self.show_upload_csv),
            right=("下一步：确认更新", self.show_execute),
            right2=("重新预览", self.do_preview),
        )
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)

        ttk.Label(page, text="第 3 步：预览更新内容", font=_bold_font(16)).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="先计算要更新的内容，不写入飞书；结果直接用表格展示。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        # 阶段流程指示器
        steps_frame = ttk.Frame(page)
        steps_frame.grid(row=2, column=0, sticky="ew", pady=(8, 12))
        self.preview_steps = self._build_step_bar(steps_frame, ["计算匹配", "生成更新", "统计结果"], current=0)

        stats = ttk.LabelFrame(page, text="预览统计", padding=14)
        stats.grid(row=3, column=0, sticky="ew")
        for col in range(4):
            stats.columnconfigure(col, weight=1)
        self.preview_stat_values = {
            "csv_rows": self._stat(stats, 0, "CSV 文件行数", "--"),
            "matched": self._stat(stats, 1, "匹配记录", "--"),
            "updates": self._stat(stats, 2, "待更新", "--"),
            "errors": self._stat(stats, 3, "异常状态", "--"),
        }

        table_area = ttk.Frame(page)
        table_area.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        table_area.columnconfigure(0, weight=1)
        table_area.columnconfigure(1, weight=1)
        table_area.rowconfigure(0, weight=1)

        field_box = ttk.LabelFrame(table_area, text="字段变更统计", padding=8)
        field_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        field_box.columnconfigure(0, weight=1)
        field_box.rowconfigure(0, weight=1)
        self.preview_field_table = ttk.Treeview(field_box, columns=("field", "count"), show="headings", height=9)
        self.preview_field_table.heading("field", text="字段")
        self.preview_field_table.heading("count", text="预计变更数量")
        self.preview_field_table.column("field", width=220)
        self.preview_field_table.column("count", width=120, anchor="center")
        self.preview_field_table.grid(row=0, column=0, sticky="nsew")

        status_box = ttk.LabelFrame(table_area, text="签收状态变更统计", padding=8)
        status_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        status_box.columnconfigure(0, weight=1)
        status_box.rowconfigure(0, weight=1)
        self.preview_status_table = ttk.Treeview(status_box, columns=("status", "count"), show="headings", height=9)
        self.preview_status_table.heading("status", text="签收状态")
        self.preview_status_table.heading("count", text="预计变更数量")
        self.preview_status_table.column("status", width=220)
        self.preview_status_table.column("count", width=120, anchor="center")
        self.preview_status_table.grid(row=0, column=0, sticky="nsew")

        self.preview_log = self._log_box(page, "预览日志", row=5)
        self.preview_log.insert("end", "正在准备预览……\n")

        self.after(100, self.do_preview)

    def do_preview(self) -> None:
        self._run_background("预览更新", self._preview_worker)

    def _preview_worker(self) -> None:
        service, config = self._build_service_and_config(self.selected_interface)
        self.log("开始读取 CSV 和飞书寄样表……")
        self.after(0, lambda: self._set_step(self.preview_steps, 0, "active"))
        result = sync_csv_to_bitable(service, config, dry_run=True, progress=self.log)
        self.preview_result_data = result.to_dict()
        self.after(0, lambda: self._set_step(self.preview_steps, 0, "done"))
        self.after(0, lambda: self._set_step(self.preview_steps, 1, "done"))
        self.after(0, lambda: self._set_step(self.preview_steps, 2, "done"))
        self.log("预览计算完成。")
        self.after(0, self._show_preview_result, result)

    def _show_preview_result(self, result: CsvSyncResult) -> None:
        self.preview_stat_values["csv_rows"].configure(text=str(result.csv_rows))
        self.preview_stat_values["matched"].configure(text=str(result.matched_records))
        self.preview_stat_values["updates"].configure(text=str(result.planned_updates))
        self.preview_stat_values["errors"].configure(text=str(sum(result.unknown_statuses.values())))

        for table in (self.preview_field_table, self.preview_status_table):
            for item in table.get_children():
                table.delete(item)
        for field_name, count in sorted(result.field_changes.items(), key=lambda x: -x[1]):
            self.preview_field_table.insert("", "end", values=(field_name, count))
        for status, count in sorted(result.status_changes.items(), key=lambda x: -x[1]):
            self.preview_status_table.insert("", "end", values=(status, count))

        if result.unknown_statuses:
            names = "、".join(result.unknown_statuses.keys())
            messagebox.showwarning("发现未匹配状态", f"CSV 中存在未配置的签收状态：{names}\n请先补充规则后再更新。")
        else:
            messagebox.showinfo("预览完成", f"预览完成：共 {len(self.csv_paths)} 个 CSV 文件，预计更新 {result.planned_updates} 条。")

    # ── 第 4 步：执行 ──────────────────────────────

    def show_execute(self) -> None:
        self.clear_content()
        self.set_status("确认执行更新")
        self._set_action_buttons(
            left=("上一步：预览", self.show_preview),
            right=("执行更新", self.do_execute),
        )
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)

        ttk.Label(page, text="第 4 步：确认执行更新", font=_bold_font(16)).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="确认预览无误后，再写入飞书寄样表。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        confirm = ttk.LabelFrame(page, text="执行前确认", padding=16)
        confirm.grid(row=2, column=0, sticky="ew")
        for text in ["已选择飞书接口", "已选择 CSV 文件", "已预览更新内容", "确认 CSV 文件空值可以覆盖飞书原值"]:
            ttk.Checkbutton(confirm, text=text).pack(anchor="w", pady=4)

        # 阶段流程指示器
        steps_frame = ttk.Frame(page)
        steps_frame.grid(row=3, column=0, sticky="ew", pady=(12, 8))
        self.execute_steps = self._build_step_bar(steps_frame, ["准备数据", "写入飞书", "完成"], current=0)

        self.execute_log = self._log_box(page, "执行日志", row=4)
        self.execute_log.insert("end", "点击「执行更新」后开始。\n")

    def do_execute(self) -> None:
        if not messagebox.askyesno("确认执行", "确定要更新到飞书寄样表吗？\n\nCSV 空值会覆盖飞书原值，仅「签收状态」按规则映射。确定继续吗？"):
            return
        self.execute_log.delete("1.0", tk.END)
        self._set_step(self.execute_steps, 0, "active")
        self._run_background(
            "执行更新",
            self._execute_worker,
            on_ok=lambda: messagebox.showinfo("更新完成", "飞书寄样表更新完成。"),
        )

    def _execute_worker(self) -> None:
        service, config = self._build_service_and_config(self.selected_interface)
        self.via_log("开始执行更新……")
        self.after(0, lambda: self._set_step(self.execute_steps, 0, "done"))
        self.after(0, lambda: self._set_step(self.execute_steps, 1, "active"))

        def progress(msg: str, current: int, total_count: int) -> None:
            self.via_log(msg)

        result = sync_csv_to_bitable(service, config, dry_run=False, progress=progress)
        self.after(0, lambda: self._set_step(self.execute_steps, 1, "done"))
        self.after(0, lambda: self._set_step(self.execute_steps, 2, "done"))
        self.via_log(f"更新完成：成功 {result.updated} 条，失败 {len(result.errors)} 条。")
        if result.errors:
            for rid, err in result.errors[:10]:
                self.via_log(f"  失败：{rid} —— {err}")
            if len(result.errors) > 10:
                self.via_log(f"  ... 还有 {len(result.errors) - 10} 条失败")

    # ── 服务构建 ───────────────────────────────────

    def _build_service_and_config(self, interface_data: dict[str, str] | None) -> tuple[BitableService, CsvSyncConfig]:
        if not interface_data:
            raise ValueError("尚未选择飞书接口")

        app_id = interface_data["app_id"].strip()
        app_secret = interface_data["app_secret"].strip()
        app_token = interface_data["app_token"].strip()
        table_id = interface_data["table_id"].strip()

        if not all([app_id, app_secret, app_token, table_id]):
            raise ValueError("飞书接口信息不完整，请检查。")

        saved = load_window_config()
        rules_path = Path(saved.get("rules_path") or default_rules_path())

        if not self.csv_paths:
            raise ValueError("请先上传至少一个 CSV 文件")

        # 合并多个 CSV 到临时文件
        if len(self.csv_paths) == 1:
            csv_path = Path(self.csv_paths[0])
        else:
            csv_path = self._merge_csv_files()

        service = BitableService(FeishuClient(FeishuConfig(app_id=app_id, app_secret=app_secret), timeout=30))
        config = CsvSyncConfig(app_token=app_token, table_id=table_id, csv_path=csv_path, rules_path=rules_path)
        return service, config

    def _merge_csv_files(self) -> Path:
        """合并多个 CSV 文件到临时文件，去重表头。"""
        import csv
        import tempfile

        from .csv_sync import read_text_with_fallback

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig", newline="")
        writer = None
        fieldnames = None
        for path in self.csv_paths:
            text = read_text_with_fallback(Path(path))
            reader = csv.DictReader(text.splitlines())
            if not reader.fieldnames:
                continue
            if fieldnames is None:
                fieldnames = reader.fieldnames
                writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
            for row in reader:
                if writer and fieldnames:
                    writer.writerow({name: row.get(name, "") for name in fieldnames})
        tmp.close()
        return Path(tmp.name)

    # ── 后台线程 / 日志 ────────────────────────────

    def _run_background(
        self,
        title: str,
        worker: Callable[[], None],
        on_ok: Callable[[], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.log(f"{title}开始。")
        self._start_spinner(title)

        def target() -> None:
            try:
                worker()
                self.log(f"{title}完成。")
                if on_ok:
                    self.after(0, on_ok)
            except Exception as exc:  # noqa: BLE001
                self.log(f"{title}失败：{exc}")
                if on_error:
                    self.after(0, lambda exc=exc: on_error(exc))
                else:
                    self.after(0, lambda: messagebox.showerror(title, str(exc)))
            finally:
                self.after(0, self._stop_spinner)
                self.after(0, self._restore_status)

        threading.Thread(target=target, daemon=True).start()

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def via_log(self, message: str) -> None:
        """直接在 execute_log 中追加，同时写入队列。"""
        self.log_queue.put(message)

    def _restore_status(self) -> None:
        self.status_var.set(self._saved_status)

    def _start_spinner(self, title: str) -> None:
        self._spinning = True
        self._spinner_idx = 0
        self.status_var.set(f"◐ {title}中……")

        def tick() -> None:
            if not self._spinning:
                return
            ch = self._spinner_chars[self._spinner_idx % len(self._spinner_chars)]
            self._spinner_idx += 1
            text = f"{ch} {title}中……"
            self.status_var.set(text)
            self.spinner_label.configure(text=text)
            self.spinner_label.place(relx=0.5, rely=0.45, anchor="center")
            self.after(120, tick)

        tick()

    def _stop_spinner(self) -> None:
        self._spinning = False
        self.spinner_label.place_forget()

    def set_status(self, text: str) -> None:
        self._saved_status = text
        self.status_var.set(text)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if hasattr(self, "execute_log") and self.execute_log.winfo_exists():
                self.execute_log.insert(tk.END, f"{message}\n")
                self.execute_log.see(tk.END)
            if hasattr(self, "preview_log") and self.preview_log.winfo_exists():
                self.preview_log.insert(tk.END, f"{message}\n")
                self.preview_log.see(tk.END)
        self.after(100, self._drain_log_queue)

    # ── 通用组件 ───────────────────────────────────

    def _build_step_bar(self, parent: ttk.Frame, labels: list[str], current: int) -> list[tk.Frame]:
        """构建圆点+连线步骤条，返回每个步骤的 Frame 列表。"""
        steps: list[tk.Frame] = []
        for i, label in enumerate(labels):
            sf = ttk.Frame(parent)
            sf.pack(side="left", expand=True, fill="x")
            dot_canvas = tk.Canvas(sf, width=24, height=24, highlightthickness=0, background="SystemButtonFace")
            dot_canvas.pack(pady=(4, 0))
            dot = dot_canvas.create_oval(2, 2, 22, 22, fill="#d0d0d0", outline="")
            dot_canvas.dot_id = dot
            sf._dot_canvas = dot_canvas
            sf._label_text = label
            lbl = ttk.Label(sf, text=label, foreground="#999999", font=_font(9), anchor="center")
            lbl.pack(pady=(2, 0))
            sf._label = lbl
            steps.append(sf)
        return steps

    def _set_step(self, steps: list[tk.Frame], index: int, state: str) -> None:
        """设置步骤状态：pending / active / done"""
        if index >= len(steps):
            return
        sf = steps[index]
        if state == "done":
            sf._dot_canvas.itemconfigure(sf._dot_canvas.dot_id, fill="#4CAF50")
            sf._label.configure(foreground="#4CAF50", font=_font(9))
        elif state == "active":
            sf._dot_canvas.itemconfigure(sf._dot_canvas.dot_id, fill="#2196F3")
            sf._label.configure(foreground="#2196F3", font=_bold_font(9))
        else:
            sf._dot_canvas.itemconfigure(sf._dot_canvas.dot_id, fill="#d0d0d0")
            sf._label.configure(foreground="#999999", font=_font(9))

    def _entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, secret: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(parent, textvariable=variable, show="*" if secret else "").grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=8)

    def _stat(self, parent: ttk.Frame, col: int, label: str, value: str) -> ttk.Label:
        box = ttk.Frame(parent, padding=8)
        box.grid(row=0, column=col, sticky="ew", padx=4)
        ttk.Label(box, text=label, foreground="#666666").pack(anchor="center")
        value_label = ttk.Label(box, text=value, font=_bold_font(18))
        value_label.pack(anchor="center", pady=(4, 0))
        return value_label

    def _log_box(self, parent: ttk.Frame, title: str, row: int = 3) -> tk.Text:
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.grid(row=row, column=0, sticky="nsew", pady=(14, 0))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        log = tk.Text(box, wrap="word")
        log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        log.configure(yscrollcommand=scrollbar.set)
        return log


def main() -> None:
    app = CsvUpdaterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
