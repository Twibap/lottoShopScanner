from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import load_rankings_to_postgres as loader  # noqa: E402


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")


class RowConversionTests(unittest.TestCase):
    def test_draw_and_repeated_shop_events_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            draws = root / "draws.jsonl"
            shops = root / "shops.jsonl"
            draw = {
                "ltEpsd": 10, "ltRflYmd": "20260103",
                "rnk1WnNope": 2, "rnk1WnAmt": 1000, "rnk1SumWnAmt": 2000,
                "rnk2WnNope": 1, "rnk2WnAmt": 100, "rnk2SumWnAmt": 100,
            }
            write_jsonl(draws, [draw])
            write_jsonl(shops, [{"draw": 10, "data": {"list": [
                {"rnum": 1, "ltShpId": "A", "wnShpRnk": 1, "shpNm": "A점"},
                {"rnum": 2, "ltShpId": "A", "wnShpRnk": 1, "shpNm": "A점"},
                {"rnum": 3, "ltShpId": "B", "wnShpRnk": 2, "shpNm": "B점"},
            ]}}])

            draw_rows, prizes = loader.load_prize_map(draws)
            pairs = list(loader.shop_and_event_rows(shops, prizes))

            self.assertEqual(len(draw_rows), 1)
            self.assertEqual(prizes[10], (1000, 100))
            self.assertEqual([pair[1][1] for pair in pairs], [1, 2, 3])
            self.assertEqual([pair[1][4] for pair in pairs], [1000, 1000, 100])
            self.assertEqual([pair[1][2] for pair in pairs], ["A", "A", "B"])

    def test_missing_prize_draw_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shops.jsonl"
            write_jsonl(path, [{"draw": 11, "data": {"list": [
                {"rnum": 1, "ltShpId": "A", "wnShpRnk": 1},
            ]}}])
            with self.assertRaisesRegex(ValueError, "11회차 당첨금 정보"):
                list(loader.shop_and_event_rows(path, {10: (1000, 100)}))


if __name__ == "__main__":
    unittest.main()
