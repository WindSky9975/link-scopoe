from __future__ import annotations

import os
import queue
import stat
from datetime import datetime
from threading import Event

from .models import (
    EVENT_DONE,
    EVENT_ENTRY,
    EVENT_STATUS,
    LINK_TYPE_DIR_SYMLINK,
    LINK_TYPE_FILE_SYMLINK,
    LINK_TYPE_JUNCTION,
    LinkEntry,
    ScanEvent,
)

FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
IO_REPARSE_TAG_SYMLINK = getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C)
IO_REPARSE_TAG_MOUNT_POINT = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)


def scan_links(root_path: str, output_queue: "queue.Queue[ScanEvent]", stop_event: Event) -> None:
    root_path = os.path.abspath(os.path.expanduser(os.path.expandvars(root_path)))
    directories_scanned = 0
    links_found = 0
    queued_directories: list[str] = [root_path]

    output_queue.put(
        ScanEvent(
            kind=EVENT_STATUS,
            message=f"正在扫描：{root_path}",
            directories_scanned=directories_scanned,
            links_found=links_found,
        )
    )

    while queued_directories and not stop_event.is_set():
        current_directory = queued_directories.pop()
        directories_scanned += 1

        if directories_scanned == 1 or directories_scanned % 40 == 0:
            output_queue.put(
                ScanEvent(
                    kind=EVENT_STATUS,
                    message=(
                        f"已扫描 {directories_scanned} 个文件夹，"
                        f"发现 {links_found} 个链接"
                    ),
                    directories_scanned=directories_scanned,
                    links_found=links_found,
                )
            )

        try:
            with os.scandir(current_directory) as iterator:
                for item in iterator:
                    if stop_event.is_set():
                        break

                    try:
                        item_stat = item.stat(follow_symlinks=False)
                    except PermissionError:
                        output_queue.put(
                            ScanEvent(
                                kind=EVENT_STATUS,
                                message=f"访问被拒绝：{item.path}",
                                directories_scanned=directories_scanned,
                                links_found=links_found,
                            )
                        )
                        continue
                    except FileNotFoundError:
                        continue
                    except OSError as exc:
                        output_queue.put(
                            ScanEvent(
                                kind=EVENT_STATUS,
                                message=f"已跳过 {item.path}：{exc}",
                                directories_scanned=directories_scanned,
                                links_found=links_found,
                            )
                        )
                        continue

                    try:
                        item_is_directory = item.is_dir(follow_symlinks=False)
                    except OSError:
                        item_is_directory = False

                    if _is_reparse_point(item_stat):
                        link_entry = _build_link_entry(item.path, item_stat)
                        if link_entry is not None:
                            links_found += 1
                            output_queue.put(
                                ScanEvent(
                                    kind=EVENT_ENTRY,
                                    entry=link_entry,
                                    directories_scanned=directories_scanned,
                                    links_found=links_found,
                                )
                            )
                            continue
                        if item_is_directory:
                            queued_directories.append(item.path)
                        continue

                    if item_is_directory:
                        queued_directories.append(item.path)
        except PermissionError:
            output_queue.put(
                ScanEvent(
                    kind=EVENT_STATUS,
                    message=f"访问被拒绝：{current_directory}",
                    directories_scanned=directories_scanned,
                    links_found=links_found,
                )
            )
        except FileNotFoundError:
            continue
        except OSError as exc:
            output_queue.put(
                ScanEvent(
                    kind=EVENT_STATUS,
                    message=f"已跳过 {current_directory}：{exc}",
                    directories_scanned=directories_scanned,
                    links_found=links_found,
                )
            )

    stopped = stop_event.is_set()
    summary = (
        f"扫描已停止。共扫描 {directories_scanned} 个文件夹，发现 "
        f"{links_found} 个链接。"
        if stopped
        else f"扫描完成。共扫描 {directories_scanned} 个文件夹，发现 "
        f"{links_found} 个链接。"
    )
    output_queue.put(
        ScanEvent(
            kind=EVENT_DONE,
            message=summary,
            directories_scanned=directories_scanned,
            links_found=links_found,
            stopped=stopped,
        )
    )


def _build_link_entry(path: str, item_stat: os.stat_result) -> LinkEntry | None:
    link_type = _link_type_from_stat(item_stat)
    if not link_type:
        return None

    raw_target = ""
    resolved_target = ""
    error = ""
    try:
        raw_target = os.readlink(path)
        resolved_target = _resolve_link_target(path, raw_target)
    except OSError as exc:
        error = str(exc)

    target_exists = bool(resolved_target) and os.path.exists(resolved_target)
    return LinkEntry(
        path=os.path.abspath(path),
        link_type=link_type,
        target=resolved_target or _clean_windows_target(raw_target),
        target_exists=target_exists,
        modified_at=datetime.fromtimestamp(item_stat.st_mtime),
        raw_target=raw_target,
        error=error,
    )


def _is_reparse_point(item_stat: os.stat_result) -> bool:
    return bool(getattr(item_stat, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def _link_type_from_stat(item_stat: os.stat_result) -> str:
    reparse_tag = getattr(item_stat, "st_reparse_tag", 0)
    is_directory = stat.S_ISDIR(item_stat.st_mode)

    if reparse_tag == IO_REPARSE_TAG_MOUNT_POINT:
        return LINK_TYPE_JUNCTION
    if reparse_tag == IO_REPARSE_TAG_SYMLINK and is_directory:
        return LINK_TYPE_DIR_SYMLINK
    if reparse_tag == IO_REPARSE_TAG_SYMLINK:
        return LINK_TYPE_FILE_SYMLINK
    return ""


def _resolve_link_target(link_path: str, raw_target: str) -> str:
    cleaned_target = _clean_windows_target(raw_target)
    if not cleaned_target:
        return ""
    if os.path.isabs(cleaned_target):
        return os.path.normpath(cleaned_target)
    return os.path.normpath(
        os.path.abspath(os.path.join(os.path.dirname(link_path), cleaned_target))
    )


def _clean_windows_target(raw_target: str) -> str:
    if raw_target.startswith("\\\\?\\UNC\\"):
        return "\\" + raw_target[7:]
    if raw_target.startswith("\\\\?\\"):
        return raw_target[4:]
    if raw_target.startswith("\\??\\"):
        return raw_target[4:]
    return raw_target
