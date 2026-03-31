from __future__ import annotations

import os


def normalize_path(path: str) -> str:
    """Strip, unquote, expand ~/%VAR%, and resolve to absolute path."""
    cleaned = path.strip().strip('"')
    if not cleaned:
        return ""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(cleaned)))


def expand_path(path: str) -> str:
    """Strip, unquote, expand ~/%VAR% without resolving to absolute."""
    cleaned = path.strip().strip('"')
    if not cleaned:
        return ""
    return os.path.expandvars(os.path.expanduser(cleaned))
