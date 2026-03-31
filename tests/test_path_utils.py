import os
import unittest

from link_manager.path_utils import expand_path, normalize_path


class NormalizePathTests(unittest.TestCase):
    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(normalize_path(""), "")
        self.assertEqual(normalize_path("   "), "")

    def test_strips_surrounding_quotes(self) -> None:
        result = normalize_path('"C:\\temp\\file.txt"')
        self.assertEqual(result, os.path.abspath("C:\\temp\\file.txt"))

    def test_strips_whitespace(self) -> None:
        result = normalize_path("  C:\\temp  ")
        self.assertEqual(result, os.path.abspath("C:\\temp"))

    def test_returns_absolute_path(self) -> None:
        result = normalize_path(".\\main.py")
        self.assertEqual(result, os.path.abspath(".\\main.py"))

    def test_relative_path_resolved(self) -> None:
        result = normalize_path("some\\relative\\path")
        self.assertTrue(os.path.isabs(result))


class ExpandPathTests(unittest.TestCase):
    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(expand_path(""), "")
        self.assertEqual(expand_path("   "), "")

    def test_strips_surrounding_quotes(self) -> None:
        result = expand_path('"C:\\temp\\file.txt"')
        self.assertEqual(result, "C:\\temp\\file.txt")

    def test_does_not_resolve_to_absolute(self) -> None:
        result = expand_path("relative\\path")
        self.assertEqual(result, "relative\\path")


if __name__ == "__main__":
    unittest.main()
