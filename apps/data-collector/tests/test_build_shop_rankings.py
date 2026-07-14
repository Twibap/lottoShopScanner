from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import build_shop_rankings as rankings  # noqa: E402


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def shop(shop_id: str, rank: int, name: str, address: str = "주소") -> dict[str, object]:
    return {
        "ltShpId": shop_id, "wnShpRnk": rank, "shpNm": name, "shpAddr": address,
        "region": "서울", "shpLat": 37.5, "shpLot": 127.0,
    }


class RankingTests(unittest.TestCase):
    def test_aggregates_duplicate_winning_games_and_assigns_competition_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            draws = root / "draws.jsonl"
            shops = root / "shops.jsonl"
            output = root / "rankings.jsonl"
            write_jsonl(draws, [
                {"ltEpsd": 10, "rnk1WnAmt": 1000, "rnk2WnAmt": 100},
                {"ltEpsd": 11, "rnk1WnAmt": 2000, "rnk2WnAmt": 200},
            ])
            write_jsonl(shops, [
                {"draw": 10, "data": {"list": [
                    shop("A", 1, "옛 상호"), shop("A", 1, "옛 상호"), shop("B", 1, "B점"),
                    shop("C", 2, "C점"),
                ]}},
                {"draw": 11, "data": {"list": [
                    shop("A", 2, "새 상호", "새 주소"), shop("B", 1, "B점"),
                    shop("C", 2, "C점"),
                ]}},
            ])

            self.assertEqual(rankings.build_rankings(shops, draws, output), 3)
            records = {item["shopId"]: item for item in (
                json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()
            )}

            self.assertEqual(records["A"]["firstCount"], 2)
            self.assertEqual(records["A"]["secondCount"], 1)
            self.assertEqual(records["A"]["totalPrize"], 2200)
            self.assertEqual(records["A"]["name"], "새 상호")
            self.assertEqual(records["A"]["address"], "새 주소")
            self.assertEqual(records["A"]["firstRank"], 1)
            self.assertEqual(records["B"]["firstRank"], 1)
            self.assertEqual(records["C"]["firstRank"], 3)
            self.assertEqual(records["C"]["secondCount"], 2)
            self.assertEqual(records["C"]["winningDrawCount"], 2)

    def test_rejects_missing_draw_prize(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            draws = root / "draws.jsonl"
            shops = root / "shops.jsonl"
            write_jsonl(draws, [{"ltEpsd": 10, "rnk1WnAmt": 1000, "rnk2WnAmt": 100}])
            write_jsonl(shops, [{"draw": 11, "data": {"list": [shop("A", 1, "A점")]}}])
            with self.assertRaisesRegex(ValueError, "11회차 당첨금 정보"):
                rankings.aggregate_shops(shops, rankings.load_prizes(draws))

    def test_rejects_duplicate_shop_draw_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            draws = root / "draws.jsonl"
            shops = root / "shops.jsonl"
            write_jsonl(draws, [{"ltEpsd": 10, "rnk1WnAmt": 1000, "rnk2WnAmt": 100}])
            record = {"draw": 10, "data": {"list": [shop("A", 1, "A점")]}}
            write_jsonl(shops, [record, record])
            with self.assertRaisesRegex(ValueError, "10회차가 중복"):
                rankings.aggregate_shops(shops, rankings.load_prizes(draws))


if __name__ == "__main__":
    unittest.main()
