from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import fetch_draw_results as collector  # noqa: E402


def draw_record(draw: int) -> dict[str, object]:
    record: dict[str, object] = {
        "ltEpsd": draw, "ltRflYmd": "20260627", "bnsWnNo": 45,
    }
    record.update({f"tm{number}WnNo": number for number in range(1, 7)})
    for rank in range(1, 6):
        record[f"rnk{rank}WnNope"] = rank * 10
        record[f"rnk{rank}WnAmt"] = rank * 1000
        record[f"rnk{rank}SumWnAmt"] = rank * rank * 10000
    return record


class FakeHeaders(dict):
    def get_content_charset(self) -> str:
        return "utf-8"


class FakeResponse:
    headers = FakeHeaders()

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FetchDrawTests(unittest.TestCase):
    def test_selects_requested_draw_from_multi_draw_response(self) -> None:
        payload = {"data": {"list": [draw_record(1232), draw_record(1231), draw_record(1230)]}}
        with patch.object(collector, "urlopen", return_value=FakeResponse(payload)):
            result = collector.fetch_draw(1230, 1, 0, 0)
        self.assertEqual(result["ltEpsd"], 1230)
        self.assertNotIn("data", result)

    def test_missing_requested_draw_is_rejected(self) -> None:
        payload = {"data": {"list": [draw_record(1232)]}}
        with (
            patch.object(collector, "urlopen", return_value=FakeResponse(payload)),
            self.assertRaisesRegex(RuntimeError, "DRAW_NOT_FOUND"),
        ):
            collector.fetch_draw(1230, 1, 0, 0)

    def test_missing_prize_field_is_rejected(self) -> None:
        record = draw_record(1230)
        del record["rnk2WnAmt"]
        with self.assertRaisesRegex(RuntimeError, "rnk2WnAmt"):
            collector.validate_draw(1230, record)


class ResumeTests(unittest.TestCase):
    def tearDown(self) -> None:
        for handler in collector.logger.handlers:
            handler.close()
        collector.logger.handlers.clear()

    def test_main_saves_records_and_skips_completed_draws(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "draws.jsonl"
            failures = root / "failures.jsonl"
            log_file = root / "collector.log"
            argv = ["fetch_draw_results.py", "1230", "1231", "--output", str(output),
                    "--failed-output", str(failures), "--log-file", str(log_file),
                    "--delay", "0", "--max-delay", "0"]
            with (
                patch.object(sys, "argv", argv),
                patch.object(collector, "fetch_draw", side_effect=lambda draw, *_: draw_record(draw))
                as fetch,
            ):
                self.assertEqual(collector.main(), 0)
                self.assertEqual(fetch.call_count, 2)

            with patch.object(sys, "argv", argv), patch.object(collector, "fetch_draw") as fetch:
                self.assertEqual(collector.main(), 0)
                fetch.assert_not_called()

            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["ltEpsd"] for record in records], [1230, 1231])
            for handler in collector.logger.handlers:
                handler.close()
            collector.logger.handlers.clear()


if __name__ == "__main__":
    unittest.main()
