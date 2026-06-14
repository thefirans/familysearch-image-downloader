import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from downloader import (
    DownloadError,
    _detect_axis_length,
    normalize_cookie_header,
    parse_familysearch_url,
)


class ParseFamilySearchUrlTests(unittest.TestCase):
    def test_parses_regular_url(self) -> None:
        document = parse_familysearch_url(
            "https://www.familysearch.org/ark:/61903/3:1:3Q9M-CSMV-T5ZR?i=611&cc=3656669"
        )

        self.assertEqual(document.ark_id, "3:1:3Q9M-CSMV-T5ZR")
        self.assertEqual(document.page_number, 612)
        self.assertEqual(
            document.filename, "familysearch_3Q9M-CSMV-T5ZR_page_612.jpg"
        )

    def test_parses_html_encoded_url(self) -> None:
        document = parse_familysearch_url(
            "https://www.familysearch.org/ark:/61903/3:1:3Q9M-CSMZ-RLSS"
            "?i=1201&amp%3Bcc=3656669&amp%3Bcat=737653&lang=en"
        )

        self.assertEqual(document.ark_id, "3:1:3Q9M-CSMZ-RLSS")
        self.assertEqual(document.page_number, 1202)

    def test_rejects_other_domains(self) -> None:
        with self.assertRaises(DownloadError):
            parse_familysearch_url(
                "https://example.com/ark:/61903/3:1:3Q9M-CSMV-T5ZR?i=611"
            )


class CookieHeaderTests(unittest.TestCase):
    def test_accepts_header_prefix(self) -> None:
        self.assertEqual(
            normalize_cookie_header("Cookie: fssessionid=abc; test=123"),
            "fssessionid=abc; test=123",
        )

    def test_rejects_multiline_header(self) -> None:
        with self.assertRaises(DownloadError):
            normalize_cookie_header("fssessionid=abc\nInjected: value")


class FakeTileClient:
    def __init__(self, columns: int, rows: int) -> None:
        self.columns = columns
        self.rows = rows

    def probe(self, level: int, column: int, row: int):
        if column >= self.columns or row >= self.rows:
            return None
        return b"tile", (256, 256)


class GridDetectionTests(unittest.TestCase):
    def test_detects_columns_with_bounded_probes(self) -> None:
        with TemporaryDirectory() as directory:
            columns = _detect_axis_length(
                FakeTileClient(columns=17, rows=13),
                level=13,
                tile_dir=Path(directory),
                axis="columns",
            )

        self.assertEqual(columns, 17)

    def test_detects_rows_with_bounded_probes(self) -> None:
        with TemporaryDirectory() as directory:
            rows = _detect_axis_length(
                FakeTileClient(columns=17, rows=13),
                level=13,
                tile_dir=Path(directory),
                axis="rows",
            )

        self.assertEqual(rows, 13)


if __name__ == "__main__":
    unittest.main()
