"""飞书寄样表更新工具完整窗口原型。"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class WindowPrototype(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("飞书寄样表更新工具")
        self.geometry("980x680")
        self.minsize(900, 620)
        self.interfaces = [
            {"name": "寄样表接口 - 主账号", "app_id": "cli_xxx********", "app_token": "bascnxxx********", "table_id": "tblRWlmlvudYAruS", "status": "可用"},
            {"name": "备用接口", "app_id": "cli_yyy********", "app_token": "bascnyyy********", "table_id": "tblxxxxxxxxxxxx", "status": "未测试"},
        ]
        self.selected_interface: dict[str, str] | None = None
        self.csv_paths: list[str] = []
        self.csv_path = tk.StringVar()
        self.content = ttk.Frame(self)
        self.preview_stat_values: dict[str, ttk.Label] = {}
        self.status_var = tk.StringVar(value="请选择飞书接口")
        self._build_shell()
        self.show_select_interface()

    def _build_shell(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(22, 10, 22, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="飞书寄样表更新工具", font=("Microsoft YaHei UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="选择接口 → 上传 CSV 文件 → 预览检查 → 确认更新", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.content = ttk.Frame(self, padding=(22, 2, 22, 8))
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        footer = ttk.Frame(self, padding=(22, 0, 22, 16))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var, foreground="#555555").grid(row=0, column=0, sticky="w")

    def clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def show_select_interface(self) -> None:
        self.clear_content()
        self.status_var.set("请选择飞书接口")
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=3)
        page.columnconfigure(1, weight=2)
        page.rowconfigure(1, weight=1)

        title = ttk.Frame(page)
        title.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(title, text="第 1 步：选择飞书接口", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(title, text="选择已有接口，或者新建一个飞书接口。", foreground="#666666").pack(anchor="w", pady=(6, 0))

        list_box = ttk.LabelFrame(page, text="已保存接口", padding=14)
        list_box.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        list_box.columnconfigure(0, weight=1)
        list_box.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(list_box)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(0, weight=1)
        ttk.Entry(toolbar).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(toolbar, text="搜索", command=lambda: messagebox.showinfo("搜索", "原型提示：这里以后会按接口名称搜索。" )).grid(row=0, column=1)

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
        self.interface_menu.add_command(label="编辑选中接口", command=lambda: messagebox.showinfo("编辑", "原型提示：后续这里进入编辑接口界面。"))
        self.interface_menu.add_command(label="删除选中接口", command=self.delete_selected_interface)
        for item in self.interfaces:
            self.interface_table.insert("", "end", values=(item["name"], item["table_id"], item["status"]))

        side = ttk.Frame(page)
        side.grid(row=1, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        action_box = ttk.LabelFrame(side, text="接口操作", padding=16)
        action_box.grid(row=0, column=0, sticky="ew")
        ttk.Label(action_box, text="双击左侧接口即可使用；也可以先选中后测试、编辑或删除。", wraplength=280, foreground="#555555").pack(anchor="w")
        ttk.Button(action_box, text="测试选中接口", command=self.test_selected_interface).pack(fill="x", pady=(14, 8))
        ttk.Button(action_box, text="编辑选中接口", command=lambda: messagebox.showinfo("编辑", "原型提示：后续这里进入编辑接口界面。" )).pack(fill="x", pady=(0, 8))
        ttk.Button(action_box, text="删除选中接口", command=self.delete_selected_interface).pack(fill="x")

        new_box = ttk.LabelFrame(side, text="没有接口？", padding=16)
        new_box.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(new_box, text="新建一个飞书接口后，下次打开会出现在左侧列表里。", wraplength=280, foreground="#555555").pack(anchor="w")
        ttk.Button(new_box, text="新建飞书接口", command=self.show_create_interface).pack(fill="x", pady=(16, 0))

        detail_box = ttk.LabelFrame(side, text="下一步", padding=16)
        detail_box.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(detail_box, text="选择接口后，进入上传 CSV 文件。", wraplength=280).pack(anchor="w")
        ttk.Button(detail_box, text="下一步：上传 CSV 文件", command=self.go_upload_from_select).pack(fill="x", pady=(16, 0))

    def show_create_interface(self) -> None:
        self.clear_content()
        self.status_var.set("新建飞书接口")
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)

        ttk.Label(page, text="新建飞书接口", font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="填写飞书应用和多维表格信息，保存后回到接口选择。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        form = ttk.LabelFrame(page, text="接口信息", padding=18)
        form.grid(row=2, column=0, sticky="new")
        form.columnconfigure(1, weight=1)

        self.name_var = tk.StringVar()
        self.app_id_var = tk.StringVar()
        self.app_secret_var = tk.StringVar()
        self.app_token_var = tk.StringVar()
        self.table_id_var = tk.StringVar()
        self._entry(form, 0, "接口名称", self.name_var)
        self._entry(form, 1, "App ID", self.app_id_var)
        self._entry(form, 2, "App Secret", self.app_secret_var, secret=True)
        self._entry(form, 3, "App Token", self.app_token_var)
        self._entry(form, 4, "Table ID", self.table_id_var)

        buttons = ttk.Frame(form)
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        ttk.Button(buttons, text="测试连接", command=self.test_new_interface).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="保存接口", command=self.save_new_interface).pack(side="left")

        help_box = ttk.LabelFrame(page, text="填写说明", padding=14)
        help_box.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        for text in ["App ID / App Secret 来自飞书开放平台自建应用。", "App Token 是多维表格 app_token。", "Table ID 是寄样表的数据表 ID，通常以 tbl 开头。"]:
            ttk.Label(help_box, text=f"• {text}", foreground="#555555").pack(anchor="w", pady=2)

        footer = ttk.Frame(page)
        footer.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        ttk.Button(footer, text="返回接口选择", command=self.show_select_interface).pack(side="left")
        ttk.Button(footer, text="保存并使用", command=self.save_and_use_new_interface).pack(side="right")

    def show_upload_csv(self) -> None:
        self.clear_content()
        name = self.selected_interface["name"] if self.selected_interface else "未选择"
        self.status_var.set(f"当前接口：{name}")
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)

        ttk.Label(page, text="第 2 步：上传 CSV 文件", font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="可以一次选择多个 TikTok Manage orders CSV 文件，三个店铺的CSV 文件可同时上传。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        box = ttk.LabelFrame(page, text="CSV 文件", padding=18)
        box.grid(row=2, column=0, sticky="nsew")
        page.rowconfigure(2, weight=1)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)

        top = ttk.Frame(box)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(0, weight=1)
        self.csv_count_var = tk.StringVar(value="已选择 CSV 文件：0 个")
        ttk.Label(top, textvariable=self.csv_count_var).grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="添加 CSV 文件", command=self.choose_csv).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(top, text="清空列表", command=self.clear_csv_files).grid(row=0, column=2, padx=(8, 0))

        drop_hint = ttk.Label(
            box,
            text="三个店铺的CSV 文件可同时上传\n可直接拖到此区域，或点击右上角添加CSV 文件",
            anchor="center",
            justify="center",
            foreground="#333333",
            font=("Microsoft YaHei UI", 13, "bold"),
        )
        drop_hint.grid(row=1, column=0, sticky="ew", pady=(4, 12), ipady=10)

        self.csv_table = ttk.Treeview(box, columns=("file",), show="headings", height=8)
        self.csv_table.heading("file", text="CSV 文件路径")
        self.csv_table.column("file", width=780)
        self.csv_table.grid(row=2, column=0, sticky="nsew")
        self.csv_table.bind("<Button-3>", self.show_csv_context_menu)
        self.csv_menu = tk.Menu(self, tearoff=0)
        self.csv_menu.add_command(label="删除选中CSV 文件", command=self.delete_selected_csv_file)
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=self.csv_table.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.csv_table.configure(yscrollcommand=scrollbar.set)

        hint = ttk.LabelFrame(page, text="说明", padding=12)
        hint.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(hint, text="规则文件不需要在这里选择，程序内部固定使用当前更新规则。多个 CSV 文件会合并后一起匹配订单 ID；选中文件后右键可单独删除。", foreground="#555555").pack(anchor="w")

        footer = ttk.Frame(page)
        footer.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        ttk.Button(footer, text="上一步：选择接口", command=self.show_select_interface).pack(side="left")
        ttk.Button(footer, text="下一步：预览更新", command=self.go_preview).pack(side="right")

    def show_preview(self) -> None:
        self.clear_content()
        self.status_var.set("预览更新内容")
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)

        ttk.Label(page, text="第 3 步：预览更新内容", font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="先计算要更新的内容，不写入飞书；结果直接用表格展示。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        stats = ttk.LabelFrame(page, text="预览统计", padding=14)
        stats.grid(row=2, column=0, sticky="ew")
        for col in range(4):
            stats.columnconfigure(col, weight=1)
        self.preview_stat_values = {
            "csv_rows": self._stat(stats, 0, "CSV 文件行数", "--"),
            "matched": self._stat(stats, 1, "匹配记录", "--"),
            "updates": self._stat(stats, 2, "待更新", "--"),
            "errors": self._stat(stats, 3, "异常状态", "--"),
        }

        table_area = ttk.Frame(page)
        table_area.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
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

        actions = ttk.Frame(page)
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="上一步：上传 CSV 文件", command=self.show_upload_csv).pack(side="left")
        ttk.Button(actions, text="开始预览", command=self.preview_result).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="下一步：确认更新", command=self.show_execute).pack(side="right")

    def show_execute(self) -> None:
        self.clear_content()
        self.status_var.set("确认执行更新")
        page = ttk.Frame(self.content)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)

        ttk.Label(page, text="第 4 步：确认执行更新", font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="确认预览无误后，再写入飞书寄样表。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(6, 10))

        confirm = ttk.LabelFrame(page, text="执行前确认", padding=16)
        confirm.grid(row=2, column=0, sticky="ew")
        for text in ["已选择飞书接口", "已选择 CSV 文件", "已预览更新内容", "确认 CSV 文件空值可以覆盖飞书原值"]:
            ttk.Checkbutton(confirm, text=text).pack(anchor="w", pady=4)

        log = self._log_box(page, "执行日志")
        log.insert("end", "点击“执行更新”后，这里显示更新进度和最终结果。\n")

        actions = ttk.Frame(page)
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="上一步：预览", command=self.show_preview).pack(side="left")
        ttk.Button(actions, text="执行更新", command=lambda: self.execute_result(log)).pack(side="right")

    def use_selected_interface(self) -> None:
        selected = self.interface_table.selection()
        if not selected:
            messagebox.showwarning("请选择接口", "请先在左侧列表中选择一个飞书接口。")
            return
        index = self.interface_table.index(selected[0])
        self.selected_interface = self.interfaces[index]
        messagebox.showinfo("已选择接口", f"已选择：{self.selected_interface['name']}")
        self.show_upload_csv()

    def show_interface_context_menu(self, event: tk.Event) -> None:
        item = self.interface_table.identify_row(event.y)
        if item:
            self.interface_table.selection_set(item)
            self.interface_menu.tk_popup(event.x_root, event.y_root)

    def test_selected_interface(self) -> None:
        selected = self.interface_table.selection()
        if not selected:
            messagebox.showwarning("请选择接口", "请先选择接口，再测试连接。")
            return
        messagebox.showinfo("测试连接", "原型提示：接口连接测试通过。")

    def delete_selected_interface(self) -> None:
        selected = self.interface_table.selection()
        if not selected:
            messagebox.showwarning("请选择接口", "请先选择要删除的接口。")
            return
        if messagebox.askyesno("确认删除", "确定删除选中的飞书接口吗？"):
            index = self.interface_table.index(selected[0])
            if 0 <= index < len(self.interfaces):
                del self.interfaces[index]
            self.interface_table.delete(selected[0])
            messagebox.showinfo("已删除", "原型提示：接口已删除。")

    def go_upload_from_select(self) -> None:
        if not self.selected_interface:
            messagebox.showwarning("缺少接口", "请先选择一个飞书接口，或新建并使用。")
            return
        self.show_upload_csv()

    def test_new_interface(self) -> None:
        if not self._validate_new_interface():
            return
        messagebox.showinfo("测试连接", "原型提示：新接口连接测试通过。")

    def save_new_interface(self) -> None:
        if not self._validate_new_interface():
            return
        self.interfaces.append(self._new_interface_data())
        messagebox.showinfo("保存成功", "飞书接口已保存。")
        self.show_select_interface()

    def save_and_use_new_interface(self) -> None:
        if not self._validate_new_interface():
            return
        data = self._new_interface_data()
        self.interfaces.append(data)
        self.selected_interface = data
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
        for value, message in checks:
            if not value:
                messagebox.showwarning("信息不完整", message)
                return False
        return True

    def _new_interface_data(self) -> dict[str, str]:
        return {
            "name": self.name_var.get().strip(),
            "app_id": self.app_id_var.get().strip(),
            "app_token": self.app_token_var.get().strip(),
            "table_id": self.table_id_var.get().strip(),
            "status": "未测试",
        }

    def choose_csv(self) -> None:
        paths = filedialog.askopenfilenames(title="选择一个或多个 CSV 文件", filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not paths:
            return
        for path in paths:
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
            messagebox.showwarning("请选择CSV 文件", "请先选中要删除的CSV 文件。")
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

    def preview_result(self) -> None:
        for key, value in {"csv_rows": "6344", "matched": "465", "updates": "342", "errors": "0"}.items():
            self.preview_stat_values[key].configure(text=value)
        for table in (self.preview_field_table, self.preview_status_table):
            for item in table.get_children():
                table.delete(item)
        for field, count in [("签收日期", "342"), ("物流单号", "36"), ("联系方式", "17"), ("签收状态", "88"), ("查询日期", "88")]:
            self.preview_field_table.insert("", "end", values=(field, count))
        for status, count in [("运输中", "47"), ("已签收", "41"), ("已发布", "1")]:
            self.preview_status_table.insert("", "end", values=(status, count))
        messagebox.showinfo("预览完成", f"预览完成：共 {len(self.csv_paths)} 个CSV 文件，预计更新 342 条。")

    def execute_result(self, log: tk.Text) -> None:
        if not messagebox.askyesno("确认执行", "确定要更新到飞书寄样表吗？"):
            return
        log.insert("end", "开始执行更新...\n")
        log.insert("end", "原型提示：成功更新 342 条，失败 0 条。\n")
        messagebox.showinfo("更新完成", "更新完成：成功 342 条，失败 0 条。")

    def _entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, secret: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(parent, textvariable=variable, show="*" if secret else "").grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=8)

    def _stat(self, parent: ttk.Frame, col: int, label: str, value: str) -> ttk.Label:
        box = ttk.Frame(parent, padding=8)
        box.grid(row=0, column=col, sticky="ew", padx=4)
        ttk.Label(box, text=label, foreground="#666666").pack(anchor="center")
        value_label = ttk.Label(box, text=value, font=("Microsoft YaHei UI", 18, "bold"))
        value_label.pack(anchor="center", pady=(4, 0))
        return value_label

    def _log_box(self, parent: ttk.Frame, title: str) -> tk.Text:
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        log = tk.Text(box, wrap="word")
        log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        log.configure(yscrollcommand=scrollbar.set)
        return log


def main() -> None:
    app = WindowPrototype()
    app.mainloop()


if __name__ == "__main__":
    main()
