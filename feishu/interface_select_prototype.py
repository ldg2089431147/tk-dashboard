"""飞书接口选择窗口原型。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class InterfaceSelectPrototype(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("选择飞书接口 - 窗口原型")
        self.geometry("860x560")
        self.minsize(780, 500)
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(22, 18, 22, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="选择飞书接口", font=("Microsoft YaHei UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="请选择一个已保存的飞书接口；如果没有，就新建一个接口。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(8, 0))

        body = ttk.Frame(self, padding=(22, 8, 22, 14))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        list_box = ttk.LabelFrame(body, text="已保存接口", padding=14)
        list_box.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_box.columnconfigure(0, weight=1)
        list_box.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(list_box)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(0, weight=1)
        ttk.Entry(toolbar).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(toolbar, text="搜索").grid(row=0, column=1)

        table = ttk.Treeview(list_box, columns=("name", "table", "status"), show="headings", height=10)
        table.heading("name", text="接口名称")
        table.heading("table", text="Table ID")
        table.heading("status", text="状态")
        table.column("name", width=210)
        table.column("table", width=180)
        table.column("status", width=80, anchor="center")
        table.grid(row=1, column=0, sticky="nsew")
        table.insert("", "end", values=("寄样表接口 - 主账号", "tblRWlmlvudYAruS", "可用"))
        table.insert("", "end", values=("备用接口", "tblxxxxxxxxxxxx", "未测试"))

        table_scroll = ttk.Scrollbar(list_box, orient="vertical", command=table.yview)
        table_scroll.grid(row=1, column=1, sticky="ns")
        table.configure(yscrollcommand=table_scroll.set)

        table_buttons = ttk.Frame(list_box)
        table_buttons.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(table_buttons, text="使用选中接口").pack(side="left", padx=(0, 8))
        ttk.Button(table_buttons, text="测试接口").pack(side="left", padx=(0, 8))
        ttk.Button(table_buttons, text="编辑").pack(side="left", padx=(0, 8))
        ttk.Button(table_buttons, text="删除").pack(side="left")

        side = ttk.Frame(body)
        side.grid(row=0, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        new_box = ttk.LabelFrame(side, text="没有接口？", padding=16)
        new_box.grid(row=0, column=0, sticky="ew")
        ttk.Label(new_box, text="新建一个飞书接口后，下次打开会出现在左侧列表里。", wraplength=260, foreground="#555555").grid(row=0, column=0, sticky="w")
        ttk.Button(new_box, text="新建飞书接口", width=22).grid(row=1, column=0, sticky="ew", pady=(16, 0))

        detail_box = ttk.LabelFrame(side, text="接口详情", padding=16)
        detail_box.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        details = [
            ("接口名称", "寄样表接口 - 主账号"),
            ("App ID", "cli_xxx********"),
            ("App Token", "bascnxxx********"),
            ("Table ID", "tblRWlmlvudYAruS"),
            ("最后测试", "2026-06-16 通过"),
        ]
        for index, (label, value) in enumerate(details):
            ttk.Label(detail_box, text=label, foreground="#666666").grid(row=index, column=0, sticky="w", pady=4)
            ttk.Label(detail_box, text=value).grid(row=index, column=1, sticky="w", padx=(12, 0), pady=4)

        tips = ttk.LabelFrame(side, text="说明", padding=16)
        tips.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        side.rowconfigure(2, weight=1)
        ttk.Label(tips, text="这里先只负责选择飞书接口。选择完成后，再进入上传 CSV 的下一步。", wraplength=260, foreground="#555555").pack(anchor="w")

        footer = ttk.Frame(self, padding=(22, 0, 22, 18))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Button(footer, text="取消").pack(side="left")
        ttk.Button(footer, text="下一步：上传 CSV").pack(side="right")


def main() -> None:
    app = InterfaceSelectPrototype()
    app.mainloop()


if __name__ == "__main__":
    main()
