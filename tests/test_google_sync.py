import unittest
import sys
from pathlib import Path
sys.path.insert(0, r"c:\Users\tscho\OneDrive\Miscellaneous\Headshot Booth Project")

from src.google_forms_sync import normalize_google_sheets_url

class TestGoogleSync(unittest.TestCase):
    def test_edit_url_normalization(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing"
        expected = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv"
        self.assertEqual(normalize_google_sheets_url(url), expected)

    def test_edit_url_with_gid(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=987654321"
        expected = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv&gid=987654321"
        self.assertEqual(normalize_google_sheets_url(url), expected)

    def test_pub_url_preserved(self):
        url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZcuPPQFGrEJnGffV9fOIFXLUZXEBnf2U7k0A3_z6gOujpXWiI60CIWTitoXyjTObKZ79QHUdQ_YMc/pub?output=csv"
        self.assertEqual(normalize_google_sheets_url(url), url)

    def test_export_url_preserved(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv"
        self.assertEqual(normalize_google_sheets_url(url), url)

if __name__ == "__main__":
    unittest.main()
