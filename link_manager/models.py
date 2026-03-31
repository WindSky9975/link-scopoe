"""数据模型定义。

包含链接条目 (LinkEntry)、扫描事件 (ScanEvent) 的数据类，
以及链接类型和事件类型的常量。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime


# ── 链接类型常量 ──

LINK_TYPE_JUNCTION = "目录联接 (Junction)"
LINK_TYPE_DIR_SYMLINK = "目录符号链接 (Directory Symlink)"
LINK_TYPE_FILE_SYMLINK = "文件符号链接 (File Symlink)"
SUPPORTED_LINK_TYPES = (
    LINK_TYPE_JUNCTION,
    LINK_TYPE_DIR_SYMLINK,
    LINK_TYPE_FILE_SYMLINK,
)

# ── 扫描事件类型常量 ──

EVENT_ENTRY = "entry"      # 发现一个链接条目
EVENT_STATUS = "status"    # 扫描进度状态更新
EVENT_DONE = "done"        # 扫描完成


@dataclass(slots=True)
class LinkEntry:
    """表示一个已发现的链接（联接或符号链接）。"""

    path: str                # 链接自身的路径
    link_type: str           # 链接类型（Junction / Dir Symlink / File Symlink）
    target: str              # 解析后的目标路径
    target_exists: bool      # 目标路径是否存在
    modified_at: datetime    # 链接的修改时间
    raw_target: str = ""     # 原始目标路径（未清理的 Windows 设备路径）
    error: str = ""          # 读取链接时的错误信息（为空表示正常）

    @property
    def name(self) -> str:
        """链接名称（路径的最后一段）。"""
        return os.path.basename(os.path.normpath(self.path)) or self.path

    @property
    def parent(self) -> str:
        """链接所在的父目录。"""
        normalized_path = os.path.normpath(self.path)
        return os.path.dirname(normalized_path) or self.path

    @property
    def modified_display(self) -> str:
        """格式化的修改时间字符串。"""
        return self.modified_at.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def status_text(self) -> str:
        """链接状态的中文描述。"""
        if self.error:
            return "读取失败"
        return "正常" if self.target_exists else "目标缺失"

    @property
    def is_directory_link(self) -> bool:
        """是否为目录类型的链接（联接或目录符号链接）。"""
        return self.link_type in (LINK_TYPE_JUNCTION, LINK_TYPE_DIR_SYMLINK)


@dataclass(slots=True)
class ScanEvent:
    """扫描线程与 GUI 主线程之间通信的事件消息。"""

    kind: str                            # 事件类型：entry / status / done
    message: str = ""                    # 状态消息文本
    entry: LinkEntry | None = None       # 发现的链接条目（仅 entry 事件）
    directories_scanned: int = 0         # 已扫描的文件夹数
    links_found: int = 0                 # 已发现的链接数
    stopped: bool = False                # 是否因用户中止而结束
