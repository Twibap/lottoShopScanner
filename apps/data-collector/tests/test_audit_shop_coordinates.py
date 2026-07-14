from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import audit_shop_coordinates as coordinate_audit  # noqa: E402


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


class CoordinateAuditTests(unittest.TestCase):
    def test_classifies_coordinate_issues_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rankings.jsonl"
            write_jsonl(path, [
                {"shopId": "A", "latitude": 37.5, "longitude": 127.0},
                {"shopId": "B", "latitude": 37.5, "longitude": 127.0},
                {"shopId": "C", "latitude": None, "longitude": None},
                {"shopId": "D", "latitude": "37.5", "longitude": 127.0},
                {"shopId": "E", "latitude": 0, "longitude": 0},
                {"shopId": "F", "latitude": 19.5, "longitude": 118.0},
                {"shopId": "G", "name": "인터넷 복권판매사이트",
                 "address": "동행복권(dhlottery.co.kr)",
                 "latitude": 37.4, "longitude": 127.1},
            ])

            report = coordinate_audit.audit(path)

            self.assertEqual(report["summary"], {
                "totalShops": 7, "validCoordinateShops": 3,
                "missingCoordinates": 1, "nonNumericCoordinates": 1,
                "zeroCoordinates": 1, "outsideKoreaBounds": 1,
                "duplicateCoordinateGroups": 1, "shopsInDuplicateGroups": 2,
                "nonPhysicalCandidates": 1,
                "criticalIssues": 4,
            })
            duplicate = report["issues"]["duplicateCoordinates"][0]
            self.assertEqual([shop["shopId"] for shop in duplicate["shops"]], ["A", "B"])
            self.assertEqual(
                report["issues"]["nonPhysicalCandidates"][0]["shopId"], "G"
            )

    def test_accepts_boundary_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rankings.jsonl"
            write_jsonl(path, [
                {"shopId": "A", "latitude": 32.0, "longitude": 124.0},
                {"shopId": "B", "latitude": 39.0, "longitude": 132.0},
            ])

            report = coordinate_audit.audit(path)

            self.assertEqual(report["summary"]["validCoordinateShops"], 2)
            self.assertEqual(report["summary"]["nonPhysicalCandidates"], 0)
            self.assertEqual(report["summary"]["criticalIssues"], 0)


if __name__ == "__main__":
    unittest.main()
