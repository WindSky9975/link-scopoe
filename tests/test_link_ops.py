import os
import unittest

from link_manager.link_ops import _expand_user_path, _normalize_user_path, _resolve_input_target


class LinkOpsHelperTests(unittest.TestCase):
    def test_expand_user_path_trims_quotes(self) -> None:
        self.assertEqual(_expand_user_path('"C:\\temp\\file.txt"'), r"C:\temp\file.txt")

    def test_normalize_user_path_returns_absolute_path(self) -> None:
        expected = os.path.abspath(r".\main.py")
        self.assertEqual(_normalize_user_path(r".\main.py"), expected)

    def test_resolve_input_target_uses_link_parent_for_relative_paths(self) -> None:
        self.assertEqual(
            _resolve_input_target(r"C:\links\shortcut", r"..\targets\docs"),
            r"C:\targets\docs",
        )
        self.assertEqual(
            _resolve_input_target(r"C:\links\shortcut", r"D:\targets\docs"),
            r"D:\targets\docs",
        )


if __name__ == "__main__":
    unittest.main()
