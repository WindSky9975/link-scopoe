from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime


LINK_TYPE_JUNCTION = "目录联接 (Junction)"
LINK_TYPE_DIR_SYMLINK = "目录符号链接"
LINK_TYPE_FILE_SYMLINK = "文件符号链接"
SUPPORTED_LINK_TYPES = (
    LINK_TYPE_JUNCTION,
    LINK_TYPE_DIR_SYMLINK,
    LINK_TYPE_FILE_SYMLINK,
)

EVENT_ENTRY = "entry"
EVENT_STATUS = "status"
EVENT_DONE = "done"


@dataclass(slots=True)
class LinkEntry:
    path: str
    link_type: str
    target: str
    target_exists: bool
    modified_at: datetime
    raw_target: str = ""
    error: str = ""

    @property
    def name(self) -> str:
        return self.path.rstrip("\\/").split("\\")[-1] or self.path

    @property
    def parent(self) -> str:
        normalized_path = os.path.normpath(self.path)
        return os.path.dirname(normalized_path) or self.path

    @property
    def modified_display(self) -> str:
        return self.modified_at.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def status_text(self) -> str:
        if self.error:
            return "读取失败"
        return "正常" if self.target_exists else "目标缺失"

    @property
    def is_directory_link(self) -> bool:
        return self.link_type in (LINK_TYPE_JUNCTION, LINK_TYPE_DIR_SYMLINK)


@dataclass(slots=True)
class ScanEvent:
    kind: str
    message: str = ""
    entry: LinkEntry | None = None
    directories_scanned: int = 0
    links_found: int = 0
    stopped: bool = False
