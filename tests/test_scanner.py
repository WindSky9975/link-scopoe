import stat
import unittest
from types import SimpleNamespace

from link_manager.models import LINK_TYPE_DIR_SYMLINK, LINK_TYPE_FILE_SYMLINK, LINK_TYPE_JUNCTION
from link_manager.scanner import (
    IO_REPARSE_TAG_MOUNT_POINT,
    IO_REPARSE_TAG_SYMLINK,
    _clean_windows_target,
    _link_type_from_stat,
    _resolve_link_target,
)


class ScannerHelperTests(unittest.TestCase):
    def test_clean_windows_target_removes_device_prefixes(self) -> None:
        self.assertEqual(
            _clean_windows_target(r"\\?\UNC\server\share"),
            r"\\server\share",
        )
        self.assertEqual(_clean_windows_target(r"\\?\C:\temp"), r"C:\temp")
        self.assertEqual(_clean_windows_target(r"\??\C:\temp"), r"C:\temp")

    def test_resolve_link_target_handles_absolute_and_relative_paths(self) -> None:
        self.assertEqual(
            _resolve_link_target(r"C:\links\docs", r"D:\targets\docs"),
            r"D:\targets\docs",
        )
        self.assertEqual(
            _resolve_link_target(r"C:\links\docs", r"..\targets\docs"),
            r"C:\targets\docs",
        )

    def test_link_type_from_stat_detects_supported_reparse_points(self) -> None:
        junction_stat = SimpleNamespace(
            st_reparse_tag=IO_REPARSE_TAG_MOUNT_POINT,
            st_mode=stat.S_IFDIR | 0o755,
        )
        dir_symlink_stat = SimpleNamespace(
            st_reparse_tag=IO_REPARSE_TAG_SYMLINK,
            st_mode=stat.S_IFDIR | 0o755,
        )
        file_symlink_stat = SimpleNamespace(
            st_reparse_tag=IO_REPARSE_TAG_SYMLINK,
            st_mode=stat.S_IFREG | 0o644,
        )

        self.assertEqual(_link_type_from_stat(junction_stat), LINK_TYPE_JUNCTION)
        self.assertEqual(_link_type_from_stat(dir_symlink_stat), LINK_TYPE_DIR_SYMLINK)
        self.assertEqual(_link_type_from_stat(file_symlink_stat), LINK_TYPE_FILE_SYMLINK)


if __name__ == "__main__":
    unittest.main()
