"""链接操作模块。

提供链接的创建、删除、打开和定位功能，
包含 Windows 特定的错误码处理和权限提示。
"""

from __future__ import annotations

import os
import stat
import subprocess

from .models import LINK_TYPE_DIR_SYMLINK, LINK_TYPE_FILE_SYMLINK, LINK_TYPE_JUNCTION
from .path_utils import expand_path, normalize_path

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # 隐藏子进程窗口
FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class LinkOperationError(RuntimeError):
    """链接操作失败时抛出的异常，携带用户友好的中文错误信息。"""


def create_link(link_path: str, target_path: str, link_type: str) -> tuple[str, str]:
    """创建链接。根据 link_type 创建联接或符号链接，返回 (链接路径, 目标路径)。"""
    link_path = _normalize_user_path(link_path)
    target_path = _expand_user_path(target_path)

    if not link_path:
        raise LinkOperationError("必须填写链接路径。")
    if not target_path:
        raise LinkOperationError("必须填写目标路径。")

    link_parent = os.path.dirname(link_path)
    if not os.path.isdir(link_parent):
        raise LinkOperationError("链接的父目录不存在。")
    if os.path.lexists(link_path):
        raise LinkOperationError("链接路径已存在。")

    resolved_target = _resolve_input_target(link_path, target_path)

    if link_type == LINK_TYPE_JUNCTION:
        if not os.path.isdir(resolved_target):
            raise LinkOperationError("目录联接 (Junction) 的目标必须是已存在的文件夹。")
        _create_junction(link_path, resolved_target)
    elif link_type == LINK_TYPE_DIR_SYMLINK:
        _validate_directory_target(resolved_target)
        _create_symbolic_link(link_path, resolved_target, target_is_directory=True)
    elif link_type == LINK_TYPE_FILE_SYMLINK:
        _validate_file_target(resolved_target)
        _create_symbolic_link(link_path, resolved_target, target_is_directory=False)
    else:
        raise LinkOperationError(f"不支持的链接类型：{link_type}")

    return link_path, resolved_target


def delete_link(link_path: str) -> None:
    """删除链接（仅删除链接本身，不影响目标）。"""
    link_path = _normalize_user_path(link_path)
    if not os.path.lexists(link_path):
        raise LinkOperationError("所选链接已不存在。")

    try:
        item_stat = os.stat(link_path, follow_symlinks=False)
    except OSError as exc:
        raise LinkOperationError(_format_os_error(exc)) from exc

    if not getattr(item_stat, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
        raise LinkOperationError("所选路径不是目录联接 (Junction) 或符号链接 (Symlink)。")

    try:
        if stat.S_ISDIR(item_stat.st_mode):
            os.rmdir(link_path)
        else:
            os.unlink(link_path)
    except OSError as exc:
        raise LinkOperationError(_format_os_error(exc)) from exc


def reveal_in_explorer(path: str) -> None:
    """在 Windows 资源管理器中定位并选中指定路径。"""
    path = _normalize_user_path(path)
    if not os.path.lexists(path):
        raise LinkOperationError("所选路径已不存在。")

    try:
        subprocess.Popen(
            ["explorer", f"/select,{path}"],
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError as exc:
        raise LinkOperationError(_format_os_error(exc)) from exc


def open_target(path: str) -> None:
    """使用系统默认方式打开指定路径。"""
    path = _normalize_user_path(path)
    if not os.path.exists(path):
        raise LinkOperationError("目标路径不存在。")

    try:
        os.startfile(path)
    except OSError as exc:
        raise LinkOperationError(_format_os_error(exc)) from exc


def _create_symbolic_link(link_path: str, target_path: str, target_is_directory: bool) -> None:
    """通过 os.symlink 创建符号链接。"""
    try:
        os.symlink(target_path, link_path, target_is_directory=target_is_directory)
    except OSError as exc:
        raise LinkOperationError(_format_os_error(exc)) from exc


def _create_junction(link_path: str, target_path: str) -> None:
    """通过 cmd /c mklink /J 创建目录联接。"""
    command = ["cmd", "/c", "mklink", "/J", link_path, target_path]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "未知错误。"
        raise LinkOperationError(f"创建目录联接 (Junction) 失败。{detail}")


def _validate_directory_target(target_path: str) -> None:
    if os.path.exists(target_path) and not os.path.isdir(target_path):
        raise LinkOperationError("所选目标不是文件夹。")


def _validate_file_target(target_path: str) -> None:
    if os.path.exists(target_path) and os.path.isdir(target_path):
        raise LinkOperationError("所选目标是文件夹，不是文件。")


def _resolve_input_target(link_path: str, target_path: str) -> str:
    """解析用户输入的目标路径。相对路径基于链接所在目录解析。"""
    if os.path.isabs(target_path):
        return os.path.normpath(target_path)
    return os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(link_path), target_path)))


def _normalize_user_path(path: str) -> str:
    return normalize_path(path)


def _expand_user_path(path: str) -> str:
    return expand_path(path)


def _format_os_error(exc: OSError) -> str:
    """将 OSError 转换为用户友好的中文错误信息，特殊处理常见 Windows 错误码。"""
    if getattr(exc, "winerror", None) == 1314:
        return (
            "权限不足。创建符号链接 (Symlink) 通常需要管理员权限，或在 Windows 中启用开发者模式。"
        )
    if getattr(exc, "winerror", None) == 183:
        return "路径已存在。"
    if getattr(exc, "winerror", None) == 5:
        return "访问被拒绝。"
    return str(exc) or exc.__class__.__name__
