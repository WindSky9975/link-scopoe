from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    from link_manager.link_ops import (
        LinkOperationError,
        create_link,
        delete_link,
        open_target,
        reveal_in_explorer,
    )
    from link_manager.models import (
        EVENT_DONE,
        EVENT_ENTRY,
        EVENT_STATUS,
        LINK_TYPE_DIR_SYMLINK,
        LINK_TYPE_FILE_SYMLINK,
        LINK_TYPE_JUNCTION,
        SUPPORTED_LINK_TYPES,
        LinkEntry,
    )
    from link_manager.scanner import scan_links
else:
    from .link_ops import LinkOperationError, create_link, delete_link, open_target
    from .link_ops import reveal_in_explorer
    from .models import (
        EVENT_DONE,
        EVENT_ENTRY,
        EVENT_STATUS,
        LINK_TYPE_DIR_SYMLINK,
        LINK_TYPE_FILE_SYMLINK,
        LINK_TYPE_JUNCTION,
        SUPPORTED_LINK_TYPES,
        LinkEntry,
    )
    from .scanner import scan_links

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


class LinkManagerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("LinkScope 链接管理器")
        self.root.geometry("1320x820")
        self.root.minsize(1080, 700)
        self.root.option_add("*Font", "{Segoe UI} 10")
        self.root.configure(bg="#f2f4f8")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._configure_styles()

        self.root_path_var = tk.StringVar()
        self.type_filter_var = tk.StringVar(value=FILTER_ALL)
        self.target_drive_filter_var = tk.StringVar(value=FILTER_ALL)
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪。")
        self.summary_var = tk.StringVar(value="显示 0 / 总计 0")
        self.selection_name_var = tk.StringVar(value="-")
        self.selection_type_var = tk.StringVar(value="-")
        self.selection_status_var = tk.StringVar(value="-")
        self.selection_modified_var = tk.StringVar(value="-")

        self.entries: list[LinkEntry] = []
        self.activity_messages: list[str] = []
        self.scan_queue: "queue.Queue" = queue.Queue()
        self.scan_thread: threading.Thread | None = None
        self.scan_stop_event: threading.Event | None = None
        self.sort_column = "name"
        self.sort_descending = False
        self._visible_paths: list[str] = []
        self._updating_filters = False
        self.sidebar_host: ttk.Frame | None = None
        self.sidebar_canvas: tk.Canvas | None = None
        self.sidebar_content: ttk.Frame | None = None
        self.sidebar_window_id: int | None = None
        self.filter_comboboxes: list[ttk.Combobox] = []

        self.search_var.trace_add("write", self._handle_filter_change)
        self.type_filter_var.trace_add("write", self._handle_filter_change)
        self.target_drive_filter_var.trace_add("write", self._handle_filter_change)

        self._build_layout()
        self.root.bind_all("<Button-1>", self._handle_global_click, add="+")
        self.root.bind_all("<MouseWheel>", self._handle_global_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._handle_global_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._handle_global_mousewheel, add="+")
        self._set_action_state()

    def run(self) -> None:
        self.root.mainloop()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("App.TFrame", background="#f2f4f8")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure(
            "Header.TLabel",
            background="#f2f4f8",
            foreground="#14213d",
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "SubHeader.TLabel",
            background="#f2f4f8",
            foreground="#516176",
            font=("Segoe UI", 10),
        )
        style.configure("Section.TLabelframe", background="#ffffff", bordercolor="#d7dde7")
        style.configure(
            "Section.TLabelframe.Label",
            background="#ffffff",
            foreground="#223047",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("Status.TLabel", background="#e9edf4", foreground="#20304d", padding=(10, 8))
        style.configure("Primary.TButton", padding=(12, 8))
        style.configure("Danger.TButton", padding=(12, 8))

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, style="App.TFrame", padding=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(header, text="LinkScope", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="在 Windows 上查看并管理目录联接 (Junction) 和符号链接 (Symlink)。",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        content = ttk.Panedwindow(container, orient="horizontal")
        content.grid(row=1, column=0, sticky="nsew")

        sidebar_host = ttk.Frame(content, style="Panel.TFrame")
        sidebar_host.columnconfigure(0, weight=1)
        sidebar_host.rowconfigure(0, weight=1)
        content.add(sidebar_host, weight=0)
        sidebar = self._create_scrollable_sidebar(sidebar_host)

        results = ttk.Frame(content, style="Panel.TFrame", padding=14)
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        content.add(results, weight=1)

        self._build_sidebar(sidebar)
        self._build_results(results)

        status_bar = ttk.Label(container, textvariable=self.status_var, style="Status.TLabel", anchor="w")
        status_bar.grid(row=2, column=0, sticky="ew", pady=(14, 0))

    def _create_scrollable_sidebar(self, parent: ttk.Frame) -> ttk.Frame:
        canvas = tk.Canvas(
            parent,
            background="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas, style="Panel.TFrame", padding=14)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.columnconfigure(0, weight=1)

        content.bind("<Configure>", self._sync_sidebar_scroll_region)
        canvas.bind("<Configure>", self._sync_sidebar_canvas_width)

        self.sidebar_host = parent
        self.sidebar_canvas = canvas
        self.sidebar_content = content
        self.sidebar_window_id = window_id
        return content

    def _sync_sidebar_scroll_region(self, _event: object = None) -> None:
        if self.sidebar_canvas is None:
            return
        scroll_region = self.sidebar_canvas.bbox("all")
        if scroll_region is not None:
            self.sidebar_canvas.configure(scrollregion=scroll_region)

    def _sync_sidebar_canvas_width(self, event: object) -> None:
        if self.sidebar_canvas is None or self.sidebar_window_id is None:
            return
        width = getattr(event, "width", None)
        if width is None:
            return
        self.sidebar_canvas.itemconfigure(self.sidebar_window_id, width=width)
        self._sync_sidebar_scroll_region()

    def _handle_global_mousewheel(self, event: tk.Event) -> str | None:
        self._dismiss_open_filter_comboboxes(event.widget)

        if self.sidebar_canvas is None or not self._is_sidebar_widget(event.widget):
            return None

        units = self._mousewheel_units(event)
        if units == 0:
            return None

        if event.widget == self.activity_text:
            self.activity_text.yview_scroll(units, "units")
            return "break"

        self.sidebar_canvas.yview_scroll(units, "units")
        return "break"

    def _handle_global_click(self, event: tk.Event) -> None:
        self._dismiss_open_filter_comboboxes(event.widget)

    def _handle_filter_combobox_mousewheel(self, event: tk.Event) -> str:
        units = self._mousewheel_units(event)
        if units != 0 and self.sidebar_canvas is not None:
            self.sidebar_canvas.yview_scroll(units, "units")
        return "break"

    def _suppress_filter_combobox_key_change(self, _event: tk.Event) -> str:
        return "break"

    def _blur_filter_combobox(self, _event: object = None) -> None:
        if self.sidebar_canvas is not None:
            self.root.after_idle(self.sidebar_canvas.focus_set)

    def _configure_filter_combobox(self, combobox: ttk.Combobox) -> None:
        self.filter_comboboxes.append(combobox)
        combobox.bind("<MouseWheel>", self._handle_filter_combobox_mousewheel)
        combobox.bind("<Button-4>", self._handle_filter_combobox_mousewheel)
        combobox.bind("<Button-5>", self._handle_filter_combobox_mousewheel)
        for sequence in ("<Up>", "<Down>", "<Prior>", "<Next>", "<Home>", "<End>"):
            combobox.bind(sequence, self._suppress_filter_combobox_key_change)
        combobox.bind("<<ComboboxSelected>>", self._blur_filter_combobox, add="+")

    def _mousewheel_units(self, event: tk.Event) -> int:
        delta = getattr(event, "delta", 0)
        if delta:
            units = -int(delta / 120)
            if units == 0:
                return -1 if delta > 0 else 1
            return units

        num = getattr(event, "num", None)
        if num == 4:
            return -1
        if num == 5:
            return 1
        return 0

    def _dismiss_open_filter_comboboxes(self, widget: tk.Misc | None) -> None:
        for combobox in self.filter_comboboxes:
            if not self._is_filter_combobox_posted(combobox):
                continue
            if self._is_filter_combobox_related_widget(combobox, widget):
                continue
            self.root.tk.call("ttk::combobox::Unpost", str(combobox))

    def _is_filter_combobox_posted(self, combobox: ttk.Combobox) -> bool:
        popdown = self._filter_combobox_popdown_path(combobox)
        return bool(int(self.root.tk.call("winfo", "ismapped", popdown)))

    def _is_filter_combobox_related_widget(
        self,
        combobox: ttk.Combobox,
        widget: tk.Misc | None,
    ) -> bool:
        current = widget
        while current is not None:
            if current == combobox:
                return True
            current = current.master

        if widget is None:
            return False

        widget_path = str(widget)
        popdown = self._filter_combobox_popdown_path(combobox)
        return widget_path == popdown or widget_path.startswith(popdown + ".")

    def _filter_combobox_popdown_path(self, combobox: ttk.Combobox) -> str:
        return str(self.root.tk.call("ttk::combobox::PopdownWindow", str(combobox)))

    def _is_sidebar_widget(self, widget: tk.Misc | None) -> bool:
        current = widget
        while current is not None:
            if current == self.sidebar_host:
                return True
            current = current.master
        return False

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        scan_frame = ttk.LabelFrame(parent, text="扫描范围", style="Section.TLabelframe", padding=12)
        scan_frame.grid(row=0, column=0, sticky="ew")
        scan_frame.columnconfigure(0, weight=1)

        ttk.Label(scan_frame, text="根目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(scan_frame, textvariable=self.root_path_var).grid(row=1, column=0, sticky="ew", pady=(6, 8))
        browse_row = ttk.Frame(scan_frame)
        browse_row.grid(row=2, column=0, sticky="ew")
        browse_row.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(browse_row, text="选择", command=self._choose_root).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.scan_button = ttk.Button(browse_row, text="开始扫描", command=self._start_scan, style="Primary.TButton")
        self.scan_button.grid(row=0, column=1, sticky="ew", padx=3)
        self.stop_button = ttk.Button(browse_row, text="停止", command=self._stop_scan)
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        filter_frame = ttk.LabelFrame(parent, text="筛选", style="Section.TLabelframe", padding=12)
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        filter_frame.columnconfigure(0, weight=1)
        ttk.Label(filter_frame, text="链接类型").grid(row=0, column=0, sticky="w")
        self.type_filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.type_filter_var,
            values=(FILTER_ALL,) + SUPPORTED_LINK_TYPES,
            state="readonly",
        )
        self.type_filter_combo.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        self._configure_filter_combobox(self.type_filter_combo)
        ttk.Label(filter_frame, text="目标盘符").grid(row=2, column=0, sticky="w")
        self.target_drive_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.target_drive_filter_var,
            values=(FILTER_ALL,),
            state="readonly",
        )
        self.target_drive_combo.grid(row=3, column=0, sticky="ew", pady=(6, 8))
        self._configure_filter_combobox(self.target_drive_combo)
        ttk.Label(filter_frame, text="搜索").grid(row=4, column=0, sticky="w")
        ttk.Entry(filter_frame, textvariable=self.search_var).grid(row=5, column=0, sticky="ew", pady=(6, 8))
        ttk.Button(filter_frame, text="清空筛选", command=self._clear_filters).grid(row=6, column=0, sticky="ew")
        ttk.Label(filter_frame, textvariable=self.summary_var, foreground="#58667d").grid(row=7, column=0, sticky="w", pady=(10, 0))

        detail_frame = ttk.LabelFrame(parent, text="选中项详情", style="Section.TLabelframe", padding=12)
        detail_frame.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        detail_frame.columnconfigure(0, weight=1)
        ttk.Label(detail_frame, text="名称").grid(row=0, column=0, sticky="w")
        ttk.Entry(detail_frame, textvariable=self.selection_name_var, state="readonly").grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Label(detail_frame, text="类型").grid(row=2, column=0, sticky="w")
        ttk.Entry(detail_frame, textvariable=self.selection_type_var, state="readonly").grid(row=3, column=0, sticky="ew", pady=(4, 8))
        ttk.Label(detail_frame, text="状态").grid(row=4, column=0, sticky="w")
        ttk.Entry(detail_frame, textvariable=self.selection_status_var, state="readonly").grid(row=5, column=0, sticky="ew", pady=(4, 8))
        ttk.Label(detail_frame, text="修改时间").grid(row=6, column=0, sticky="w")
        ttk.Entry(detail_frame, textvariable=self.selection_modified_var, state="readonly").grid(row=7, column=0, sticky="ew", pady=(4, 8))
        ttk.Label(detail_frame, text="链接路径").grid(row=8, column=0, sticky="w")
        self.link_path_text = self._make_readonly_text(detail_frame, height=3)
        self.link_path_text.grid(row=9, column=0, sticky="ew", pady=(4, 8))
        ttk.Label(detail_frame, text="目标路径").grid(row=10, column=0, sticky="w")
        self.target_path_text = self._make_readonly_text(detail_frame, height=3)
        self.target_path_text.grid(row=11, column=0, sticky="ew", pady=(4, 0))

        action_frame = ttk.LabelFrame(parent, text="操作", style="Section.TLabelframe", padding=12)
        action_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        action_frame.columnconfigure((0, 1), weight=1)
        self.new_link_button = ttk.Button(action_frame, text="新建链接", command=self._create_link_dialog)
        self.new_link_button.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        self.delete_button = ttk.Button(action_frame, text="删除所选", command=self._delete_selected, style="Danger.TButton")
        self.delete_button.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 6))
        self.open_link_path_button = ttk.Button(action_frame, text="打开链接路径", command=self._open_selected_link_path)
        self.open_link_path_button.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
        self.open_target_button = ttk.Button(action_frame, text="打开目标", command=self._open_selected_target)
        self.open_target_button.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=3)
        self.copy_link_button = ttk.Button(action_frame, text="复制链接路径", command=self._copy_selected_path)
        self.copy_link_button.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(3, 0))
        self.copy_target_button = ttk.Button(action_frame, text="复制目标路径", command=self._copy_selected_target)
        self.copy_target_button.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(3, 0))

        activity_frame = ttk.LabelFrame(parent, text="操作日志", style="Section.TLabelframe", padding=12)
        activity_frame.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        activity_frame.columnconfigure(0, weight=1)
        activity_frame.rowconfigure(0, weight=1)
        self.activity_text = self._make_readonly_text(activity_frame, height=10)
        self.activity_text.grid(row=0, column=0, sticky="nsew")
        activity_scrollbar = ttk.Scrollbar(activity_frame, orient="vertical", command=self.activity_text.yview)
        activity_scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self.activity_text.configure(yscrollcommand=activity_scrollbar.set)

    def _build_results(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(toolbar, text="结果列表", font=("Segoe UI", 12, "bold")).pack(side="left")

        table_frame = ttk.Frame(parent, style="Panel.TFrame")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("name", "type", "path", "target", "status", "modified")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=24)

        headings = {
            "name": "名称",
            "type": "类型",
            "path": "链接路径",
            "target": "目标路径",
            "status": "状态",
            "modified": "修改时间",
        }
        widths = {
            "name": 180,
            "type": 160,
            "path": 260,
            "target": 260,
            "status": 120,
            "modified": 160,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column], command=lambda key=column: self._sort_by(key))
            self.tree.column(column, width=widths[column], anchor="w")

        vertical_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        horizontal_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical_scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _make_readonly_text(self, parent: tk.Misc, height: int) -> tk.Text:
        widget = tk.Text(
            parent,
            height=height,
            wrap="word",
            relief="solid",
            bd=1,
            bg="#f8fafc",
            fg="#20304d",
            insertbackground="#20304d",
        )
        widget.configure(state="disabled")
        return widget

    def _choose_root(self) -> None:
        selected = filedialog.askdirectory(
            title="选择扫描根目录",
            initialdir=self.root_path_var.get() or os.path.expanduser("~"),
        )
        if selected:
            self.root_path_var.set(selected)
            self._log_activity(f"已选择根目录：{selected}")

    def _start_scan(self) -> None:
        root_path = self.root_path_var.get().strip()
        if not root_path:
            messagebox.showerror("缺少根目录", "请先选择要扫描的根目录。")
            return
        root_path = os.path.abspath(os.path.expandvars(os.path.expanduser(root_path)))
        if not os.path.isdir(root_path):
            messagebox.showerror("根目录无效", "所选根目录不存在。")
            return
        if self._is_scanning():
            return

        self.entries.clear()
        self._refresh_tree()
        self._clear_selection_details()
        self.status_var.set(f"正在扫描：{root_path}")
        self._log_activity(f"开始扫描：{root_path}")

        self.scan_queue = queue.Queue()
        self.scan_stop_event = threading.Event()
        self.scan_thread = threading.Thread(
            target=scan_links,
            args=(root_path, self.scan_queue, self.scan_stop_event),
            daemon=True,
        )
        self.scan_thread.start()
        self._set_scan_controls(scanning=True)
        self.root.after(120, self._poll_scan_queue)

    def _stop_scan(self) -> None:
        if self.scan_stop_event:
            self.scan_stop_event.set()
            self.status_var.set("正在停止扫描...")
            self._log_activity("已请求停止扫描。")

    def _poll_scan_queue(self) -> None:
        entries_changed = False

        while True:
            try:
                event = self.scan_queue.get_nowait()
            except queue.Empty:
                break

            if event.kind == EVENT_ENTRY and event.entry is not None:
                self.entries.append(event.entry)
                entries_changed = True
            elif event.kind == EVENT_STATUS:
                self.status_var.set(event.message)
                self._log_activity(event.message)
            elif event.kind == EVENT_DONE:
                self.status_var.set(event.message)
                self._log_activity(event.message)
                self.scan_thread = None
                self.scan_stop_event = None
                self._set_scan_controls(scanning=False)

        if entries_changed:
            self._refresh_tree()

        if self._is_scanning() or not self.scan_queue.empty():
            self.root.after(120, self._poll_scan_queue)

    def _handle_filter_change(self, *_args: object) -> None:
        if self._updating_filters:
            return
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        selected_path = self._get_selected_path()
        self._refresh_target_drive_filter_options()
        filtered_entries = self._get_filtered_entries()

        self.tree.delete(*self.tree.get_children())
        self._visible_paths = []
        for index, entry in enumerate(filtered_entries):
            self._visible_paths.append(entry.path)
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    entry.name,
                    entry.link_type,
                    entry.path,
                    entry.target,
                    entry.status_text,
                    entry.modified_display,
                ),
            )

        self.summary_var.set(f"显示 {len(filtered_entries)} / 总计 {len(self.entries)}")

        if selected_path and selected_path in self._visible_paths:
            selected_iid = str(self._visible_paths.index(selected_path))
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
        else:
            self._clear_selection_details()

        self._set_action_state()

    def _get_filtered_entries(self) -> list[LinkEntry]:
        type_filter = self.type_filter_var.get().strip()
        target_drive_filter = self.target_drive_filter_var.get().strip()
        search_text = self.search_var.get().strip().lower()
        filtered: list[LinkEntry] = []

        for entry in self.entries:
            if type_filter and type_filter != FILTER_ALL and entry.link_type != type_filter:
                continue
            if not self._matches_target_drive_filter(entry, target_drive_filter):
                continue
            if search_text:
                haystack = " ".join(
                    (
                        entry.name,
                        entry.path,
                        entry.target,
                        entry.link_type,
                        entry.status_text,
                    )
                ).lower()
                if search_text not in haystack:
                    continue
            filtered.append(entry)

        sort_key = self._sort_key_for(self.sort_column)
        return sorted(filtered, key=sort_key, reverse=self.sort_descending)

    def _refresh_target_drive_filter_options(self) -> None:
        drive_values = [FILTER_ALL, *self._collect_target_drive_values()]
        current_value = self.target_drive_filter_var.get().strip() or FILTER_ALL

        self._updating_filters = True
        try:
            self.target_drive_combo.configure(values=drive_values)
            if current_value not in drive_values:
                self.target_drive_filter_var.set(FILTER_ALL)
        finally:
            self._updating_filters = False

    def _collect_target_drive_values(self) -> list[str]:
        drives = {
            drive
            for entry in self.entries
            if (drive := self._extract_target_drive(entry))
        }
        return sorted(drives)

    def _matches_target_drive_filter(self, entry: LinkEntry, target_drive_filter: str) -> bool:
        if not target_drive_filter or target_drive_filter == FILTER_ALL:
            return True
        return self._extract_target_drive(entry) == target_drive_filter

    def _extract_target_drive(self, entry: LinkEntry) -> str:
        target_value = entry.target or entry.raw_target
        drive, _ = os.path.splitdrive(target_value)
        drive = drive.upper()
        if len(drive) == 2 and drive[1] == ":" and drive[0].isalpha():
            return drive
        return ""

    def _sort_by(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = False
        self._refresh_tree()

    def _sort_key_for(self, column: str):
        if column == "type":
            return lambda entry: entry.link_type.lower()
        if column == "path":
            return lambda entry: entry.path.lower()
        if column == "target":
            return lambda entry: entry.target.lower()
        if column == "status":
            return lambda entry: entry.status_text.lower()
        if column == "modified":
            return lambda entry: entry.modified_at
        return lambda entry: entry.name.lower()

    def _on_selection_changed(self, _event: object = None) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            self._clear_selection_details()
        else:
            self.selection_name_var.set(entry.name)
            self.selection_type_var.set(entry.link_type)
            self.selection_status_var.set(entry.status_text)
            self.selection_modified_var.set(entry.modified_display)
            self._set_text(self.link_path_text, entry.path)
            self._set_text(self.target_path_text, entry.target or entry.raw_target)
        self._set_action_state()

    def _on_double_click(self, _event: object) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        self._locate_selected()

    def _create_link_dialog(self) -> None:
        if self._is_scanning():
            messagebox.showinfo("扫描进行中", "请先停止当前扫描，再新建链接。")
            return

        dialog = CreateLinkDialog(self.root, initial_folder=self.root_path_var.get().strip())
        self.root.wait_window(dialog)
        if not dialog.result:
            return

        link_type, link_path, target_path = dialog.result
        try:
            created_path, resolved_target = create_link(link_path, target_path, link_type)
        except LinkOperationError as exc:
            messagebox.showerror("创建链接失败", str(exc))
            self._log_activity(f"创建失败：{exc}")
            return

        self._log_activity(f"已创建{link_type}：{created_path} -> {resolved_target}")
        self.status_var.set(f"已创建{link_type}：{created_path}")
        self._refresh_after_mutation(created_path)

    def _delete_selected(self) -> None:
        if self._is_scanning():
            messagebox.showinfo("扫描进行中", "请先停止当前扫描，再删除链接。")
            return

        entry = self._get_selected_entry()
        if entry is None:
            messagebox.showinfo("未选择项目", "请先选择要删除的链接。")
            return

        confirmed = messagebox.askyesno(
            "删除所选链接",
            "仅删除当前选中的链接？\n\n"
            f"类型：{entry.link_type}\n"
            f"路径：{entry.path}\n\n"
            "目标路径不会被删除。",
            icon="warning",
        )
        if not confirmed:
            return

        try:
            delete_link(entry.path)
        except LinkOperationError as exc:
            messagebox.showerror("删除失败", str(exc))
            self._log_activity(f"删除失败：{exc}")
            return

        self.status_var.set(f"已删除链接：{entry.path}")
        self._log_activity(f"已删除链接：{entry.path}")
        self._refresh_after_mutation(entry.path)

    def _locate_selected(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        try:
            reveal_in_explorer(entry.path)
        except LinkOperationError as exc:
            messagebox.showerror("定位失败", str(exc))

    def _open_selected_link_path(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        try:
            open_target(entry.path)
        except LinkOperationError as exc:
            messagebox.showerror("打开链接路径失败", str(exc))

    def _open_selected_target(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        try:
            open_target(entry.target)
        except LinkOperationError as exc:
            messagebox.showerror("打开目标失败", str(exc))

    def _copy_selected_path(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        self._copy_to_clipboard(entry.path)
        self.status_var.set("已复制链接路径。")

    def _copy_selected_target(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        value = entry.target or entry.raw_target
        if not value:
            messagebox.showinfo("没有目标路径", "当前项目没有可用的目标路径。")
            return
        self._copy_to_clipboard(value)
        self.status_var.set("已复制目标路径。")

    def _refresh_after_mutation(self, changed_path: str) -> None:
        root_path = self.root_path_var.get().strip()
        if root_path:
            try:
                root_abs = os.path.abspath(root_path)
                changed_abs = os.path.abspath(changed_path)
                if os.path.commonpath([root_abs, changed_abs]) == root_abs:
                    self._start_scan()
                    return
            except ValueError:
                pass
        self._refresh_tree()

    def _clear_filters(self) -> None:
        self.type_filter_var.set(FILTER_ALL)
        self.target_drive_filter_var.set(FILTER_ALL)
        self.search_var.set("")

    def _get_selected_entry(self) -> LinkEntry | None:
        path = self._get_selected_path()
        if not path:
            return None
        for entry in self.entries:
            if entry.path == path:
                return entry
        return None

    def _get_selected_path(self) -> str:
        selection = self.tree.selection()
        if not selection:
            return ""
        selected_iid = selection[0]
        try:
            index = int(selected_iid)
        except ValueError:
            return ""
        if 0 <= index < len(self._visible_paths):
            return self._visible_paths[index]
        return ""

    def _clear_selection_details(self) -> None:
        self.selection_name_var.set("-")
        self.selection_type_var.set("-")
        self.selection_status_var.set("-")
        self.selection_modified_var.set("-")
        self._set_text(self.link_path_text, "")
        self._set_text(self.target_path_text, "")

    def _set_scan_controls(self, scanning: bool) -> None:
        self.scan_button.configure(state="disabled" if scanning else "normal")
        self.stop_button.configure(state="normal" if scanning else "disabled")
        self.new_link_button.configure(state="disabled" if scanning else "normal")
        self.delete_button.configure(state="disabled" if scanning else "normal")
        self._set_action_state()

    def _set_action_state(self) -> None:
        entry = self._get_selected_entry()
        has_selection = entry is not None

        self.open_link_path_button.configure(
            state="normal" if has_selection and entry.target_exists else "disabled"
        )
        self.copy_link_button.configure(state="normal" if has_selection else "disabled")
        self.copy_target_button.configure(
            state="normal" if has_selection and (entry.target or entry.raw_target) else "disabled"
        )
        self.open_target_button.configure(
            state="normal" if has_selection and entry.target and entry.target_exists else "disabled"
        )

        if self._is_scanning():
            self.new_link_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")

    def _copy_to_clipboard(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()

    def _log_activity(self, message: str) -> None:
        if not message:
            return
        self.activity_messages.append(message)
        self._set_text(self.activity_text, "\n".join(self.activity_messages), scroll_to_end=True)

    def _set_text(self, widget: tk.Text, value: str, scroll_to_end: bool = False) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        if scroll_to_end:
            widget.see("end")
        widget.configure(state="disabled")

    def _is_scanning(self) -> bool:
        return self.scan_thread is not None and self.scan_thread.is_alive()

    def _on_close(self) -> None:
        if self.scan_stop_event:
            self.scan_stop_event.set()
        self.root.destroy()


if __name__ == "__main__":
    LinkManagerApp().run()
