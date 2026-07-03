"""新建飞书接口窗口原型。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class InterfaceCreatePrototype(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("新建飞书接口 - 窗口原型")
        self.geometry("760x620")
        self.minsize(700, 560)
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(24, 20, 24, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="新建飞书接口", font=("Microsoft YaHei UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="填写飞书应用和多维表格信息，保存后可在接口列表中选择使用。", foreground="#666666").grid(row=1, column=0, sticky="w", pady=(8, 0))

        body = ttk.Frame(self, padding=(24, 8, 24, 16))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        form = ttk.LabelFrame(body, text="接口信息", padding=18)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        self._entry(form, 0, "接口名称", "例如：寄样表接口 - 主账号")
        self._entry(form, 1, "App ID", "飞书开放平台应用 App ID")
        self._entry(form, 2, "App Secret", "飞书开放平台应用 App Secret", secret=True)
        self._entry(form, 3, "App Token", "多维表格 App Token")
        self._entry(form, 4, "Table ID", "寄样表 Table ID")

        action_row = ttk.Frame(form)
        action_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        ttk.Button(action_row, text="测试连接").pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="保存接口").pack(side="left")

        help_box = ttk.LabelFrame(body, text="填写说明", padding=16)
        help_box.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        help_box.columnconfigure(0, weight=1)
        help_text = tk.Text(help_box, wrap="word", height=10, background="#f7f7f7")
        help_text.grid(row=0, column=0, sticky="nsew")
        help_box.rowconfigure(0, weight=1)
        help_text.insert("end", "1. 接口名称：自己起一个容易识别的名字，例如“寄样表接口 - 主账号”。\n\n")
        help_text.insert("end", "2. App ID / App Secret：来自飞书开放平台自建应用。\n\n")
        help_text.insert("end", "3. App Token：多维表格的 app_token，不是 App ID。\n\n")
        help_text.insert("end", "4. Table ID：寄样表的数据表 ID，通常以 tbl 开头。\n\n")
        help_text.insert("end", "5. 保存前可以先测试连接，确认接口权限正常。")
        help_text.configure(state="disabled")

        footer = ttk.Frame(self, padding=(24, 0, 24, 20))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Button(footer, text="返回接口选择").pack(side="left")
        ttk.Button(footer, text="保存并使用").pack(side="right")

    def _entry(self, parent: ttk.Frame, row: int, label: str, placeholder: str, secret: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=9)
        entry = ttk.Entry(parent, show="*" if secret else "")
        entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=9)
        entry.insert(0, placeholder)


def main() -> None:
    app = InterfaceCreatePrototype()
    app.mainloop()


if __name__ == "__main__":
    main()
