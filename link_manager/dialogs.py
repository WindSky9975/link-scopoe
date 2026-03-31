from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .models import (
    LINK_TYPE_DIR_SYMLINK,
    LINK_TYPE_FILE_SYMLINK,
    LINK_TYPE_JUNCTION,
    SUPPORTED_LINK_TYPES,
)

FILTER_ALL = "全部"


class CreateLinkDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, initial_folder: str = "") -> None:
        super().__init__(master)
        self.title("新建链接")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.result: tuple[str, str, str] | None = None
        self.initial_folder = initial_folder

        self.link_type_var = tk.StringVar(value=LINK_TYPE_JUNCTION)
        self.link_path_var = tk.StringVar(
            value=os.path.join(initial_folder, "新建链接") if initial_folder else ""
        )
        self.target_path_var = tk.StringVar()
        self.help_var = tk.StringVar()

        self.columnconfigure(1, weight=1)
        self._build_widgets()
        self._update_help_text()
        self.link_type_var.trace_add("write", self._on_type_changed)

    def _build_widgets(self) -> None:
        ttk.Label(self, text="链接类型").grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        type_box = ttk.Combobox(
            self,
            textvariable=self.link_type_var,
            values=SUPPORTED_LINK_TYPES,
            state="readonly",
            width=28,
        )
        type_box.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(16, 8))

        ttk.Label(self, text="链接路径").grid(row=1, column=0, sticky="w", padx=16, pady=8)
        ttk.Entry(self, textvariable=self.link_path_var).grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=8
        )
        ttk.Button(self, text="浏览", command=self._browse_link_path).grid(
            row=1, column=2, sticky="ew", padx=(0, 16), pady=8
        )

        ttk.Label(self, text="目标路径").grid(row=2, column=0, sticky="w", padx=16, pady=8)
        ttk.Entry(self, textvariable=self.target_path_var).grid(
            row=2, column=1, sticky="ew", padx=(0, 8), pady=8
        )
        ttk.Button(self, text="浏览", command=self._browse_target_path).grid(
            row=2, column=2, sticky="ew", padx=(0, 16), pady=8
        )

        ttk.Label(
            self,
            textvariable=self.help_var,
            foreground="#596579",
            wraplength=430,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=16, pady=(4, 12))

        buttons = ttk.Frame(self)
        buttons.grid(row=4, column=0, columnspan=3, sticky="e", padx=16, pady=(0, 16))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="创建", command=self._submit).pack(side="right", padx=(0, 8))

    def _on_type_changed(self, *_args: object) -> None:
        self._update_help_text()

    def _update_help_text(self) -> None:
        if self.link_type_var.get() == LINK_TYPE_JUNCTION:
            self.help_var.set(
                "目录联接 (Junction) 必须指向已存在的文件夹。"
                "符号链接 (Symlink) 可以指向暂时不存在的路径，但目录联接 (Junction) 不可以。"
            )
        elif self.link_type_var.get() == LINK_TYPE_DIR_SYMLINK:
            self.help_var.set(
                "目录符号链接 (Directory Symlink) 可以指向已存在或将来才会出现的文件夹。"
            )
        else:
            self.help_var.set(
                "文件符号链接 (File Symlink) 可以指向已存在或将来才会出现的文件。"
            )
    def _browse_link_path(self) -> None:
        if self.link_type_var.get() == LINK_TYPE_FILE_SYMLINK:
            path = filedialog.asksaveasfilename(
                title="选择链接路径",
                initialdir=self.initial_folder or None,
            )
            if path:
                self.link_path_var.set(path)
            return

        parent_folder = filedialog.askdirectory(
            title="选择父目录",
            initialdir=self.initial_folder or None,
        )
        if not parent_folder:
            return

        default_name = os.path.basename(self.link_path_var.get().rstrip("\\/")) or "新建链接"
        link_name = simpledialog.askstring(
            "链接名称",
            "请输入新链接名称：",
            parent=self,
            initialvalue=default_name,
        )
        if link_name:
            self.link_path_var.set(os.path.join(parent_folder, link_name.strip()))

    def _browse_target_path(self) -> None:
        link_type = self.link_type_var.get()
        if link_type == LINK_TYPE_FILE_SYMLINK:
            path = filedialog.askopenfilename(title="选择目标文件")
        elif link_type == LINK_TYPE_JUNCTION:
            path = filedialog.askdirectory(title="选择目标文件夹")
        else:
            parent_folder = filedialog.askdirectory(
                title="选择目标父目录",
                initialdir=self.initial_folder or None,
            )
            if not parent_folder:
                return

            default_name = os.path.basename(self.target_path_var.get().rstrip("\\/")) or "目标文件夹"
            target_name = simpledialog.askstring(
                "目标目录名称",
                "请输入目标目录名称：",
                parent=self,
                initialvalue=default_name,
            )
            if not target_name or not target_name.strip():
                return
            path = os.path.join(parent_folder, target_name.strip())
        if path:
            self.target_path_var.set(path)

    def _submit(self) -> None:
        link_type = self.link_type_var.get().strip()
        link_path = self.link_path_var.get().strip()
        target_path = self.target_path_var.get().strip()

        if not link_path:
            messagebox.showerror("缺少链接路径", "请填写链接路径。", parent=self)
            return
        if not target_path:
            messagebox.showerror("缺少目标路径", "请填写目标路径。", parent=self)
            return

        self.result = (link_type, link_path, target_path)
        self.destroy()
