import unittest
from datetime import datetime

from link_manager.models import LINK_TYPE_DIR_SYMLINK, LINK_TYPE_JUNCTION, LinkEntry


class LinkEntryTests(unittest.TestCase):
    def test_displays_core_metadata(self) -> None:
        entry = LinkEntry(
            path=r"C:\links\docs",
            link_type=LINK_TYPE_JUNCTION,
            target=r"D:\targets\docs",
            target_exists=True,
            modified_at=datetime(2026, 3, 31, 10, 30, 45),
        )

        self.assertEqual(entry.name, "docs")
        self.assertEqual(entry.parent, r"C:\links")
        self.assertEqual(entry.modified_display, "2026-03-31 10:30:45")
        self.assertEqual(entry.status_text, "\u6b63\u5e38")
        self.assertTrue(entry.is_directory_link)

    def test_error_status_takes_precedence(self) -> None:
        entry = LinkEntry(
            path=r"C:\links\broken",
            link_type=LINK_TYPE_DIR_SYMLINK,
            target="",
            target_exists=False,
            modified_at=datetime(2026, 3, 31, 10, 30, 45),
            error="permission denied",
        )

        self.assertEqual(entry.status_text, "\u8bfb\u53d6\u5931\u8d25")

    def test_missing_target_status(self) -> None:
        entry = LinkEntry(
            path=r"C:\links\missing",
            link_type=LINK_TYPE_JUNCTION,
            target=r"D:\targets\missing",
            target_exists=False,
            modified_at=datetime(2026, 3, 31, 10, 30, 45),
        )

        self.assertEqual(entry.status_text, "\u76ee\u6807\u7f3a\u5931")


if __name__ == "__main__":
    unittest.main()
