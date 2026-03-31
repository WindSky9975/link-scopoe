"""主应用窗口模块。

包含 LinkManagerApp 类，负责 GUI 布局、扫描调度、
筛选排序、右键菜单和用户交互。
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .dialogs import FILTER_ALL, CreateLinkDialog
from .link_ops import LinkOperationError, create_link, delete_link, open_target, reveal_in_explorer
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
from .path_utils import normalize_path
from .scanner import read_link_entry, scan_links

SCAN_POLL_INTERVAL_MS = 120      # 轮询扫描队列的间隔（毫秒）
WINDOW_GEOMETRY = "1320x820"     # 初始窗口尺寸
WINDOW_MIN_SIZE = (1080, 700)    # 最小窗口尺寸


class LinkManagerApp:
    """LinkScope 主应用窗口。"""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("LinkScope 链接管理器")
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(*WINDOW_MIN_SIZE)
        self.root.option_add("*Font", "{Segoe UI} 10")
        self.root.configure(bg="#f2f4f8")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._configure_styles()

        self.root_path_var = tk.StringVar()
        self.type_filter_var = tk.StringVar(value=FILTER_ALL)
        self.link_drive_filter_var = tk.StringVar(value=FILTER_ALL)
        self.target_drive_filter_var = tk.StringVar(value=FILTER_ALL)
        self.status_var = tk.StringVar(value="就绪。")
        self.summary_var = tk.StringVar(value="显示 0 / 总计 0")

        self.entries: list[LinkEntry] = []
        self.activity_messages: list[str] = []
        self.scan_queue: "queue.Queue" = queue.Queue()
        self.scan_thread: threading.Thread | None = None
        self.scan_stop_event: threading.Event | None = None
        self.sort_column = "name"
        self.sort_descending = False
        self._visible_paths: list[str] = []
        self._updating_filters = False
        self.filter_comboboxes: list[ttk.Combobox] = []

        self.type_filter_var.trace_add("write", self._handle_filter_change)
        self.link_drive_filter_var.trace_add("write", self._handle_filter_change)
        self.target_drive_filter_var.trace_add("write", self._handle_filter_change)

        self._build_layout()
        self.root.bind_all("<Button-1>", self._handle_global_click, add="+")
        self.root.bind_all("<MouseWheel>", self._handle_global_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._handle_global_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._handle_global_mousewheel, add="+")

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
        container.rowconfigure(2, weight=1)

        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(header, text="LinkScope", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="在 Windows 上查看并管理目录联接 (Junction) 和符号链接 (Symlink)。",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        scan_bar = ttk.Frame(container, style="App.TFrame")
        scan_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        scan_bar.columnconfigure(1, weight=1)
        ttk.Label(scan_bar, text="根目录：").grid(row=0, column=0, sticky="w")
        ttk.Entry(scan_bar, textvariable=self.root_path_var).grid(row=0, column=1, sticky="ew", padx=(6, 8))
        ttk.Button(scan_bar, text="选择", command=self._choose_root).grid(row=0, column=2, padx=(0, 4))
        self.scan_button = ttk.Button(scan_bar, text="开始扫描", command=self._start_scan, style="Primary.TButton")
        self.scan_button.grid(row=0, column=3, padx=4)
        self.stop_button = ttk.Button(scan_bar, text="停止", command=self._stop_scan)
        self.stop_button.grid(row=0, column=4, padx=(4, 0))

        results = ttk.Frame(container, style="Panel.TFrame", padding=14)
        results.grid(row=2, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        self._build_results(results)

        activity_frame = ttk.LabelFrame(container, text="操作日志", style="Section.TLabelframe", padding=8)
        activity_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        activity_frame.columnconfigure(0, weight=1)
        self.activity_text = self._make_readonly_text(activity_frame, height=5)
        self.activity_text.grid(row=0, column=0, sticky="ew")
        activity_scrollbar = ttk.Scrollbar(activity_frame, orient="vertical", command=self.activity_text.yview)
        activity_scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self.activity_text.configure(yscrollcommand=activity_scrollbar.set)

        status_bar = ttk.Label(container, textvariable=self.status_var, style="Status.TLabel", anchor="w")
        status_bar.grid(row=4, column=0, sticky="ew", pady=(10, 0))

    def _handle_global_mousewheel(self, event: tk.Event) -> str | None:
        self._dismiss_open_filter_comboboxes(event.widget)
        return None

    def _handle_global_click(self, event: tk.Event) -> None:
        self._dismiss_open_filter_comboboxes(event.widget)

    def _handle_filter_combobox_mousewheel(self, event: tk.Event) -> str:
        return "break"

    def _suppress_filter_combobox_key_change(self, _event: tk.Event) -> str:
        return "break"

    def _blur_filter_combobox(self, _event: object = None) -> None:
        self.root.after_idle(self.root.focus_set)

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
        """关闭所有已展开的筛选下拉框（点击或滚轮时触发）。"""
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

    def _build_results(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(toolbar, text="结果列表", font=("Segoe UI", 12, "bold")).pack(side="left")

        ttk.Label(toolbar, text="类型：").pack(side="left", padx=(18, 0))
        self.type_filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.type_filter_var,
            values=(FILTER_ALL,) + SUPPORTED_LINK_TYPES,
            state="readonly",
            width=22,
        )
        self.type_filter_combo.pack(side="left", padx=(4, 0))
        self._configure_filter_combobox(self.type_filter_combo)

        ttk.Label(toolbar, text="链接盘符：").pack(side="left", padx=(14, 0))
        self.link_drive_combo = ttk.Combobox(
            toolbar,
            textvariable=self.link_drive_filter_var,
            values=(FILTER_ALL,),
            state="readonly",
            width=8,
        )
        self.link_drive_combo.pack(side="left", padx=(4, 0))
        self._configure_filter_combobox(self.link_drive_combo)

        ttk.Label(toolbar, text="目标盘符：").pack(side="left", padx=(14, 0))
        self.target_drive_combo = ttk.Combobox(
            toolbar,
            textvariable=self.target_drive_filter_var,
            values=(FILTER_ALL,),
            state="readonly",
            width=8,
        )
        self.target_drive_combo.pack(side="left", padx=(4, 0))
        self._configure_filter_combobox(self.target_drive_combo)

        ttk.Label(toolbar, textvariable=self.summary_var, foreground="#58667d").pack(side="right")
        self.new_link_button = ttk.Button(toolbar, text="新建链接", command=self._create_link_dialog)
        self.new_link_button.pack(side="right", padx=(10, 10))

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
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="定位到资源管理器", command=self._locate_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="打开链接路径", command=self._open_selected_link_path)
        self.context_menu.add_command(label="打开目标路径", command=self._open_selected_target)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制链接路径", command=self._copy_selected_path)
        self.context_menu.add_command(label="复制目标路径", command=self._copy_selected_target)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除所选", command=self._delete_selected)

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
        """启动后台扫描线程。"""
        root_path = self.root_path_var.get().strip()
        if not root_path:
            messagebox.showerror("缺少根目录", "请先选择要扫描的根目录。")
            return
        root_path = normalize_path(root_path)
        if not os.path.isdir(root_path):
            messagebox.showerror("根目录无效", "所选根目录不存在。")
            return
        if self._is_scanning():
            return

        self.entries.clear()
        self._refresh_tree()
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
        self.root.after(SCAN_POLL_INTERVAL_MS, self._poll_scan_queue)

    def _stop_scan(self) -> None:
        if self.scan_stop_event:
            self.scan_stop_event.set()
            self.status_var.set("正在停止扫描...")
            self._log_activity("已请求停止扫描。")

    def _poll_scan_queue(self) -> None:
        """定时从扫描队列中读取事件，更新 UI。通过 root.after 循环调用。"""
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
            self.root.after(SCAN_POLL_INTERVAL_MS, self._poll_scan_queue)

    def _handle_filter_change(self, *_args: object) -> None:
        if self._updating_filters:
            return
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        """根据当前筛选条件和排序重新填充结果表格。"""
        selected_path = self._get_selected_path()
        self._refresh_drive_filter_options()
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

    def _get_filtered_entries(self) -> list[LinkEntry]:
        """按类型和盘符筛选条目，并按当前排序列排序后返回。"""
        type_filter = self.type_filter_var.get().strip()
        link_drive_filter = self.link_drive_filter_var.get().strip()
        target_drive_filter = self.target_drive_filter_var.get().strip()
        filtered: list[LinkEntry] = []

        for entry in self.entries:
            if type_filter and type_filter != FILTER_ALL and entry.link_type != type_filter:
                continue
            if not self._matches_drive_filter(self._extract_link_drive(entry), link_drive_filter):
                continue
            if not self._matches_drive_filter(self._extract_target_drive(entry), target_drive_filter):
                continue
            filtered.append(entry)

        sort_key = self._sort_key_for(self.sort_column)
        return sorted(filtered, key=sort_key, reverse=self.sort_descending)

    def _refresh_drive_filter_options(self) -> None:
        """刷新链接盘符和目标盘符下拉框的可选值。"""
        self._updating_filters = True
        try:
            link_drives = [FILTER_ALL, *self._collect_drive_values(self._extract_link_drive)]
            current_link = self.link_drive_filter_var.get().strip() or FILTER_ALL
            self.link_drive_combo.configure(values=link_drives)
            if current_link not in link_drives:
                self.link_drive_filter_var.set(FILTER_ALL)

            target_drives = [FILTER_ALL, *self._collect_drive_values(self._extract_target_drive)]
            current_target = self.target_drive_filter_var.get().strip() or FILTER_ALL
            self.target_drive_combo.configure(values=target_drives)
            if current_target not in target_drives:
                self.target_drive_filter_var.set(FILTER_ALL)
        finally:
            self._updating_filters = False

    def _collect_drive_values(self, extractor) -> list[str]:
        drives = {
            drive
            for entry in self.entries
            if (drive := extractor(entry))
        }
        return sorted(drives)

    def _matches_drive_filter(self, drive: str, drive_filter: str) -> bool:
        if not drive_filter or drive_filter == FILTER_ALL:
            return True
        return drive == drive_filter

    def _extract_link_drive(self, entry: LinkEntry) -> str:
        drive, _ = os.path.splitdrive(entry.path)
        drive = drive.upper()
        if len(drive) == 2 and drive[1] == ":" and drive[0].isalpha():
            return drive
        return ""

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

    def _on_double_click(self, _event: object) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        self._locate_selected()

    def _on_right_click(self, event: tk.Event) -> None:
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.tree.focus(row_id)

        entry = self._get_selected_entry()
        if entry is None:
            return

        has_target = bool(entry.target or entry.raw_target)
        self.context_menu.entryconfigure("打开链接路径", state="normal" if entry.target_exists else "disabled")
        self.context_menu.entryconfigure("打开目标路径", state="normal" if entry.target and entry.target_exists else "disabled")
        self.context_menu.entryconfigure("复制目标路径", state="normal" if has_target else "disabled")

        self.context_menu.tk_popup(event.x_root, event.y_root)

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

    def _with_selected_entry(self, action, error_title: str = "") -> None:
        """获取当前选中条目并执行操作，自动处理空选择和 LinkOperationError。"""
        entry = self._get_selected_entry()
        if entry is None:
            return
        try:
            action(entry)
        except LinkOperationError as exc:
            if error_title:
                messagebox.showerror(error_title, str(exc))

    def _locate_selected(self) -> None:
        self._with_selected_entry(
            lambda e: reveal_in_explorer(e.path), "定位失败"
        )

    def _open_selected_link_path(self) -> None:
        self._with_selected_entry(
            lambda e: open_target(e.path), "打开链接路径失败"
        )

    def _open_selected_target(self) -> None:
        self._with_selected_entry(
            lambda e: open_target(e.target), "打开目标路径失败"
        )

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
        """链接创建或删除后，重新读取该路径并刷新表格。"""
        changed_abs = os.path.abspath(changed_path)
        self._remove_entry_by_path(changed_abs)
        if self._is_path_under_current_root(changed_abs):
            if entry := read_link_entry(changed_abs):
                self.entries.append(entry)
        self._refresh_tree()

    def _remove_entry_by_path(self, path: str) -> None:
        self.entries = [entry for entry in self.entries if entry.path != path]

    def _is_path_under_current_root(self, path: str) -> bool:
        root_path = self.root_path_var.get().strip()
        if not root_path:
            return False

        try:
            root_abs = normalize_path(root_path)
            path_abs = os.path.abspath(path)
            return os.path.commonpath([root_abs, path_abs]) == root_abs
        except ValueError:
            return False

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

    def _set_scan_controls(self, scanning: bool) -> None:
        self.scan_button.configure(state="disabled" if scanning else "normal")
        self.stop_button.configure(state="normal" if scanning else "disabled")
        self.new_link_button.configure(state="disabled" if scanning else "normal")

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
