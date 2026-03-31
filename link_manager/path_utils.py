"""路径规范化工具函数。

提供统一的路径清理、展开和规范化逻辑，
避免各模块重复实现不一致的路径处理。
"""

from __future__ import annotations

import os


def normalize_path(path: str) -> str:
    """清理并规范化路径为绝对路径。

    处理流程：去除首尾空白 → 去除引号 → 展开 ~ → 展开环境变量 → 转为绝对路径。
    """
    cleaned = path.strip().strip('"')
    if not cleaned:
        return ""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(cleaned)))


def expand_path(path: str) -> str:
    """清理并展开路径中的 ~ 和环境变量，但不转为绝对路径。"""
    cleaned = path.strip().strip('"')
    if not cleaned:
        return ""
    return os.path.expandvars(os.path.expanduser(cleaned))
