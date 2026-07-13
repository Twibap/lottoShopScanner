from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import fetch_winning_shops as scanner  # noqa: E402


SUCCESS_PAYLOAD = {
    "resultCode": None,
    "resultMessage": None,
    "data": {"total": 1, "list": [{"shpNm": "테스트 복권방"}]},
}


class FakeHeaders(dict):
    def get_content_charset(self) -> str:
        return "utf-8"


class FakeResponse:
    def __init__(self, payload: object, *, raw: bytes | None = None) -> None:
        self.headers = FakeHeaders()
        self.body = raw if raw is not None else json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def http_error(code: int, retry_after: str | None = None) -> HTTPError:
    headers = FakeHeaders()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError("https://example.test", code, f"HTTP {code}", headers, None)


class FetchDrawTests(unittest.TestCase):
    def test_success_returns_original_json(self) -> None:
        with patch.object(scanner, "urlopen", return_value=FakeResponse(SUCCESS_PAYLOAD)):
            result = scanner.fetch_draw(1232, 1, max_retries=0, max_backoff=0)
        self.assertEqual(result, SUCCESS_PAYLOAD)

    def test_http_429_uses_retry_after_then_succeeds(self) -> None:
        responses = [http_error(429, "2"), FakeResponse(SUCCESS_PAYLOAD)]
        with (
            patch.object(scanner, "urlopen", side_effect=responses) as urlopen,
            patch.object(scanner.time, "sleep") as sleep,
            self.assertLogs(scanner.logger, level=logging.WARNING) as logs,
        ):
            result = scanner.fetch_draw(1232, 1, max_retries=1, max_backoff=10)
        self.assertEqual(result, SUCCESS_PAYLOAD)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2.0)
        self.assertIn("error_code=HTTP_429", "\n".join(logs.output))

    def test_http_404_is_not_retried(self) -> None:
        with (
            patch.object(scanner, "urlopen", side_effect=http_error(404)) as urlopen,
            self.assertRaisesRegex(RuntimeError, "error_code=HTTP_404"),
        ):
            scanner.fetch_draw(1232, 1, max_retries=5, max_backoff=0)
        self.assertEqual(urlopen.call_count, 1)

    def test_timeout_retries_and_keeps_error_code(self) -> None:
        with (
            patch.object(scanner, "urlopen", side_effect=TimeoutError("timed out")) as urlopen,
            patch.object(scanner.time, "sleep"),
            self.assertRaisesRegex(RuntimeError, "error_code=TIMEOUT"),
        ):
            scanner.fetch_draw(1232, 1, max_retries=2, max_backoff=0)
        self.assertEqual(urlopen.call_count, 3)

    def test_invalid_json_keeps_error_code(self) -> None:
        with (
            patch.object(scanner, "urlopen", return_value=FakeResponse(None, raw=b"not-json")),
            self.assertRaisesRegex(RuntimeError, "error_code=INVALID_JSON"),
        ):
            scanner.fetch_draw(1232, 1, max_retries=0, max_backoff=0)

    def test_api_error_keeps_result_code(self) -> None:
        payload = {"resultCode": "E001", "resultMessage": "server busy", "data": None}
        with (
            patch.object(scanner, "urlopen", return_value=FakeResponse(payload)),
            self.assertRaisesRegex(RuntimeError, "error_code=API_E001"),
        ):
            scanner.fetch_draw(1232, 1, max_retries=0, max_backoff=0)


class ResumeTests(unittest.TestCase):
    def tearDown(self) -> None:
        for handler in scanner.logger.handlers:
            handler.close()
        scanner.logger.handlers.clear()

    def test_main_appends_then_skips_completed_draws(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "winning_shops.jsonl"
            log_file = Path(temp_dir) / "scanner.log"
            argv = ["fetch_winning_shops.py", "1231", "1232", "--output", str(output),
                    "--log-file", str(log_file), "--delay", "0"]

            with patch.object(sys, "argv", argv), patch.object(
                scanner, "fetch_draw", return_value=SUCCESS_PAYLOAD
            ) as fetch:
                self.assertEqual(scanner.main(), 0)
                self.assertEqual(fetch.call_count, 2)

            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["draw"] for record in records], [1231, 1232])

            with patch.object(sys, "argv", argv), patch.object(scanner, "fetch_draw") as fetch:
                self.assertEqual(scanner.main(), 0)
                fetch.assert_not_called()

            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 2)
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("건너뜀: 1231회차", log_text)
            self.assertIn("건너뜀: 1232회차", log_text)

            for handler in scanner.logger.handlers:
                handler.close()
            scanner.logger.handlers.clear()


if __name__ == "__main__":
    unittest.main()
