from __future__ import annotations

import json
import logging
import socket
import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError


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

    def test_url_error_wrapping_timeout_uses_connection_timeout_code(self) -> None:
        with (
            patch.object(
                scanner,
                "urlopen",
                side_effect=URLError(TimeoutError("timed out")),
            ),
            self.assertRaisesRegex(RuntimeError, "error_code=CONNECTION_TIMEOUT"),
        ):
            scanner.fetch_draw(1232, 1, max_retries=0, max_backoff=0)

    def test_winerror_10060_uses_connection_timeout_code(self) -> None:
        reason = OSError("connection timed out")
        reason.winerror = 10060
        with (
            patch.object(scanner, "urlopen", side_effect=URLError(reason)),
            self.assertRaisesRegex(RuntimeError, "error_code=CONNECTION_TIMEOUT"),
        ):
            scanner.fetch_draw(506, 1, max_retries=0, max_backoff=0)

    def test_common_network_errors_have_specific_error_codes(self) -> None:
        cases = [
            (socket.gaierror("name resolution failed"), "DNS_ERROR"),
            (ConnectionRefusedError("connection refused"), "CONNECTION_REFUSED"),
            (ConnectionResetError("connection reset"), "CONNECTION_RESET"),
            (ConnectionAbortedError("connection aborted"), "CONNECTION_ABORTED"),
            (ssl.SSLError("certificate or TLS failure"), "TLS_ERROR"),
        ]
        for reason, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                with (
                    patch.object(scanner, "urlopen", side_effect=URLError(reason)),
                    self.assertRaisesRegex(RuntimeError, f"error_code={expected_code}"),
                ):
                    scanner.fetch_draw(506, 1, max_retries=0, max_backoff=0)

    def test_common_windows_socket_errors_have_specific_error_codes(self) -> None:
        cases = {
            10051: "NETWORK_UNREACHABLE",
            10053: "CONNECTION_ABORTED",
            10054: "CONNECTION_RESET",
            10061: "CONNECTION_REFUSED",
            10065: "HOST_UNREACHABLE",
            11001: "DNS_ERROR",
        }
        for winerror, expected_code in cases.items():
            reason = OSError("socket error")
            reason.winerror = winerror
            with self.subTest(winerror=winerror):
                with (
                    patch.object(scanner, "urlopen", side_effect=URLError(reason)),
                    self.assertRaisesRegex(RuntimeError, f"error_code={expected_code}"),
                ):
                    scanner.fetch_draw(506, 1, max_retries=0, max_backoff=0)

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
            self.assertIn("건너뜀 2개", log_text)

            for handler in scanner.logger.handlers:
                handler.close()
            scanner.logger.handlers.clear()


class ResilientCollectionTests(unittest.TestCase):
    def tearDown(self) -> None:
        for handler in scanner.logger.handlers:
            handler.close()
        scanner.logger.handlers.clear()

    def test_failed_draw_is_recorded_and_later_draw_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "output.jsonl"
            failures = Path(temp_dir) / "failures.jsonl"

            def fetch(draw: int, *_: object) -> dict[str, object]:
                if draw == 2:
                    raise RuntimeError("error_code=HTTP_500 | failed")
                return {"data": {"total": 0, "list": []}}

            with patch.object(scanner.time, "sleep"):
                failed, saved = scanner.collect_pass(
                    [1, 2, 3], "first", output, failures,
                    1, 0, 0, 0, 0, 3, 60, 300, fetcher=fetch,
                )

            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            failure_records = [json.loads(line) for line in failures.read_text(
                encoding="utf-8").splitlines()]
            self.assertEqual([record["draw"] for record in records], [1, 3])
            self.assertEqual(failed, [2])
            self.assertEqual(saved, 2)
            self.assertEqual(failure_records[0]["draw"], 2)
            self.assertEqual(failure_records[0]["phase"], "first")
            self.assertEqual(failure_records[0]["error_code"], "HTTP_500")

    def test_main_retries_only_failed_draws_after_first_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "output.jsonl"
            failures = Path(temp_dir) / "failures.jsonl"
            log_file = Path(temp_dir) / "scanner.log"
            calls: list[int] = []

            def fetch(draw: int, *_: object) -> dict[str, object]:
                calls.append(draw)
                if draw == 2 and calls.count(2) == 1:
                    raise RuntimeError("error_code=TIMEOUT | failed")
                return SUCCESS_PAYLOAD

            argv = [
                "fetch_winning_shops.py", "1", "3", "--output", str(output),
                "--failed-output", str(failures), "--log-file", str(log_file),
                "--delay", "0", "--max-delay", "0",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(scanner, "fetch_draw", side_effect=fetch),
                patch.object(scanner.time, "sleep"),
            ):
                self.assertEqual(scanner.main(), 0)

            self.assertEqual(calls, [1, 2, 3, 2])
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["draw"] for record in records], [1, 3, 2])
            for handler in scanner.logger.handlers:
                handler.close()
            scanner.logger.handlers.clear()

    def test_request_delay_is_randomized_within_configured_range(self) -> None:
        with (
            patch.object(scanner.random, "uniform", return_value=1.75) as uniform,
            patch.object(scanner.time, "sleep") as sleep,
        ):
            scanner.sleep_between_requests(1.0, 2.5)
        uniform.assert_called_once_with(1.0, 2.5)
        sleep.assert_called_once_with(1.75)

    def test_consecutive_timeouts_trigger_circuit_breaker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "output.jsonl"
            failures = Path(temp_dir) / "failures.jsonl"

            def timeout(*_: object) -> dict[str, object]:
                raise RuntimeError("error_code=CONNECTION_TIMEOUT | failed")

            with (
                patch.object(scanner.random, "uniform", return_value=120.0) as uniform,
                patch.object(scanner.time, "sleep") as sleep,
            ):
                failed, saved = scanner.collect_pass(
                    [1, 2, 3], "first", output, failures,
                    1, 0, 0, 0, 0, 3, 60, 300, fetcher=timeout,
                )

            self.assertEqual(failed, [1, 2, 3])
            self.assertEqual(saved, 0)
            uniform.assert_called_once_with(60, 300)
            sleep.assert_called_once_with(120.0)

    def test_non_timeout_failure_resets_timeout_streak(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "output.jsonl"
            failures = Path(temp_dir) / "failures.jsonl"
            errors = iter(["TIMEOUT", "HTTP_500", "TIMEOUT", "TIMEOUT"])

            def fail(*_: object) -> dict[str, object]:
                raise RuntimeError(f"error_code={next(errors)} | failed")

            with patch.object(scanner.time, "sleep") as sleep:
                scanner.collect_pass(
                    [1, 2, 3, 4], "first", output, failures,
                    1, 0, 0, 0, 0, 3, 60, 300, fetcher=fail,
                )
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
