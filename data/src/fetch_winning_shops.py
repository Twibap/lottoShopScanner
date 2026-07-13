"""Download Lotto 6/45 winning-shop results and append them as JSON Lines."""

from __future__ import annotations

import argparse
import errno
import json
import logging
import os
import random
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://www.dhlottery.co.kr/wnprchsplcsrch/selectLtWnShp.do"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_MAX_DELAY_SECONDS = 2.5
DEFAULT_MAX_RETRIES = 5
DEFAULT_MAX_BACKOFF_SECONDS = 60.0
DEFAULT_TIMEOUT_STREAK_THRESHOLD = 3
DEFAULT_COOLDOWN_MIN_SECONDS = 60.0
DEFAULT_COOLDOWN_MAX_SECONDS = 300.0
TIMEOUT_ERROR_CODES = frozenset({"TIMEOUT", "CONNECTION_TIMEOUT"})

logger = logging.getLogger("winning_shops")


def positive_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"정수여야 합니다: {raw_value!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다: {value}")
    return value


def non_negative_float(raw_value: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"숫자여야 합니다: {raw_value!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError(f"0 이상이어야 합니다: {value}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="회차별 로또 당첨 판매점을 JSONL로 수집합니다.")
    parser.add_argument("start_draw", type=positive_int, help="조회할 시작 회차")
    parser.add_argument("end_draw", type=positive_int, nargs="?", help="조회할 마지막 회차")
    parser.add_argument("--output", type=Path, help="출력 JSONL 경로")
    parser.add_argument("--failed-output", type=Path, help="실패 이력 JSONL 경로")
    parser.add_argument("--log-file", type=Path, help="로그 파일 경로")
    parser.add_argument("--delay", type=non_negative_float, default=DEFAULT_DELAY_SECONDS,
                        help="요청 간 최소 대기 시간(초)")
    parser.add_argument("--max-delay", type=non_negative_float,
                        default=DEFAULT_MAX_DELAY_SECONDS,
                        help="요청 간 최대 대기 시간(초)")
    parser.add_argument("--timeout", type=non_negative_float,
                        default=DEFAULT_TIMEOUT_SECONDS, help="요청 제한 시간(초)")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        help="요청 내부 최대 재시도 횟수")
    parser.add_argument("--max-backoff", type=non_negative_float,
                        default=DEFAULT_MAX_BACKOFF_SECONDS,
                        help="재시도 최대 대기 시간(초)")
    parser.add_argument("--timeout-streak-threshold", type=positive_int,
                        default=DEFAULT_TIMEOUT_STREAK_THRESHOLD,
                        help="전체 수집을 쉬게 할 연속 타임아웃 회차 수")
    parser.add_argument("--cooldown-min", type=non_negative_float,
                        default=DEFAULT_COOLDOWN_MIN_SECONDS,
                        help="회로 차단 최소 휴지 시간(초)")
    parser.add_argument("--cooldown-max", type=non_negative_float,
                        default=DEFAULT_COOLDOWN_MAX_SECONDS,
                        help="회로 차단 최대 휴지 시간(초)")
    return parser.parse_args()


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)


def retry_after_seconds(error: HTTPError) -> float | None:
    value = error.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def backoff_seconds(attempt: int, maximum: float) -> float:
    return min(maximum, (2 ** (attempt - 1)) + random.uniform(0, 1))


def exception_error_code(error: BaseException) -> str:
    if isinstance(error, json.JSONDecodeError):
        return "INVALID_JSON"
    if isinstance(error, TimeoutError):
        return "TIMEOUT"
    if isinstance(error, URLError):
        return network_error_code(error.reason, fallback="URL_ERROR")
    if isinstance(error, OSError):
        return network_error_code(error, fallback="CONNECTION_ERROR")
    return type(error).__name__.upper()


def network_error_code(error: object, fallback: str) -> str:
    if isinstance(error, TimeoutError):
        return "CONNECTION_TIMEOUT"
    if isinstance(error, socket.gaierror):
        return "DNS_ERROR"
    if isinstance(error, ssl.SSLError):
        return "TLS_ERROR"
    if isinstance(error, ConnectionRefusedError):
        return "CONNECTION_REFUSED"
    if isinstance(error, ConnectionResetError):
        return "CONNECTION_RESET"
    if isinstance(error, ConnectionAbortedError):
        return "CONNECTION_ABORTED"
    winerror_codes = {
        10051: "NETWORK_UNREACHABLE", 10053: "CONNECTION_ABORTED",
        10054: "CONNECTION_RESET", 10060: "CONNECTION_TIMEOUT",
        10061: "CONNECTION_REFUSED", 10065: "HOST_UNREACHABLE",
        11001: "DNS_ERROR", 11002: "DNS_ERROR", 11004: "DNS_ERROR",
    }
    winerror = getattr(error, "winerror", None)
    if winerror in winerror_codes:
        return winerror_codes[winerror]
    errno_codes = {
        errno.ECONNREFUSED: "CONNECTION_REFUSED", errno.ECONNRESET: "CONNECTION_RESET",
        errno.ECONNABORTED: "CONNECTION_ABORTED", errno.ENETUNREACH: "NETWORK_UNREACHABLE",
        errno.EHOSTUNREACH: "HOST_UNREACHABLE", errno.ETIMEDOUT: "CONNECTION_TIMEOUT",
    }
    return errno_codes.get(getattr(error, "errno", None), fallback)


def runtime_error_code(error: RuntimeError) -> str:
    marker = "error_code="
    message = str(error)
    if marker not in message:
        return "RUNTIME_ERROR"
    return message.split(marker, 1)[1].split(" |", 1)[0].strip()


def fetch_draw(draw: int, timeout: float, max_retries: int,
               max_backoff: float) -> dict[str, Any]:
    url = f"{API_URL}?{urlencode({'srchLtEpsd': draw})}"
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 lottoShopScanner/1.0",
    })
    max_attempts = max_retries + 1
    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                payload = json.loads(response.read().decode(charset))
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
                result_code = payload.get("resultCode") if isinstance(payload, dict) else None
                result_message = payload.get("resultMessage") if isinstance(payload, dict) else None
                error_code = f"API_{result_code}" if result_code is not None else "INVALID_RESPONSE"
                raise RuntimeError(
                    f"error_code={error_code} | {draw}회차 응답 오류: "
                    f"{result_message or '응답 형식이 예상과 다릅니다.'}"
                )
            return payload
        except HTTPError as exc:
            error_code = f"HTTP_{exc.code}"
            retryable = exc.code in (408, 429) or 500 <= exc.code < 600
            if not retryable or attempt == max_attempts:
                exc.close()
                raise RuntimeError(
                    f"error_code={error_code} | {draw}회차 HTTP 오류: {exc.reason}"
                ) from exc
            wait = retry_after_seconds(exc)
            if wait is None:
                wait = backoff_seconds(attempt, max_backoff)
            wait = min(wait, max_backoff)
            logger.warning("error_code=%s | %s회차 서버 오류. %.1f초 후 재시도 (%s/%s)",
                           error_code, draw, wait, attempt, max_retries)
            exc.close()
            time.sleep(wait)
        except (URLError, OSError, json.JSONDecodeError) as exc:
            error_code = exception_error_code(exc)
            if attempt == max_attempts:
                raise RuntimeError(
                    f"error_code={error_code} | {draw}회차 조회 실패 "
                    f"({max_attempts}회 시도): {exc}"
                ) from exc
            wait = backoff_seconds(attempt, max_backoff)
            logger.warning("error_code=%s | %s회차 일시적 통신 오류: %s. "
                           "%.1f초 후 재시도 (%s/%s)",
                           error_code, draw, exc, wait, attempt, max_retries)
            time.sleep(wait)
    raise AssertionError("unreachable")


def load_completed_draws(output_path: Path) -> set[int]:
    completed: set[int] = set()
    if not output_path.exists():
        return completed
    with output_path.open("r", encoding="utf-8") as output_file:
        for line_number, line in enumerate(output_file, start=1):
            if not line.strip():
                continue
            try:
                draw = json.loads(line).get("draw")
                if isinstance(draw, int):
                    completed.add(draw)
                else:
                    logger.warning("출력 파일 %s번째 줄에 유효한 draw가 없습니다.", line_number)
            except json.JSONDecodeError:
                logger.warning("출력 파일 %s번째 줄이 올바른 JSON이 아니어서 무시합니다.", line_number)
    return completed


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as output_file:
        output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        output_file.flush()
        os.fsync(output_file.fileno())


def record_failure(path: Path, draw: int, phase: str, error: RuntimeError) -> None:
    append_jsonl(path, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "draw": draw,
        "phase": phase,
        "error_code": runtime_error_code(error),
        "message": str(error),
    })


def sleep_between_requests(minimum: float, maximum: float) -> None:
    if maximum == 0:
        return
    delay = random.uniform(minimum, maximum)
    logger.debug("다음 요청까지 %.1f초 대기합니다.", delay)
    time.sleep(delay)


def collect_pass(
    draws: list[int], phase: str, output_path: Path, failed_output_path: Path,
    timeout: float, max_retries: int, max_backoff: float,
    delay_min: float, delay_max: float, timeout_streak_threshold: int,
    cooldown_min: float, cooldown_max: float,
    fetcher: Callable[[int, float, int, float], dict[str, Any]] | None = None,
) -> tuple[list[int], int]:
    if fetcher is None:
        fetcher = fetch_draw
    failed_draws: list[int] = []
    saved_count = 0
    timeout_streak = 0
    for index, draw in enumerate(draws, start=1):
        logger.info("[%s %s/%s] %s회차 조회 중...", phase, index, len(draws), draw)
        try:
            response = fetcher(draw, timeout, max_retries, max_backoff)
            append_jsonl(output_path, {"draw": draw, **response})
            saved_count += 1
            timeout_streak = 0
        except RuntimeError as exc:
            error_code = runtime_error_code(exc)
            failed_draws.append(draw)
            record_failure(failed_output_path, draw, phase, exc)
            logger.error("%s회차를 건너뜁니다: %s", draw, exc)
            timeout_streak = timeout_streak + 1 if error_code in TIMEOUT_ERROR_CODES else 0
            if timeout_streak >= timeout_streak_threshold:
                cooldown = random.uniform(cooldown_min, cooldown_max)
                logger.warning("연속 타임아웃 %s회: 전체 수집을 %.1f초 쉽니다.",
                               timeout_streak, cooldown)
                time.sleep(cooldown)
                timeout_streak = 0
        if index < len(draws):
            sleep_between_requests(delay_min, delay_max)
    return failed_draws, saved_count


def main() -> int:
    try:
        args = parse_args()
        end_draw = args.end_draw if args.end_draw is not None else args.start_draw
        if args.start_draw > end_draw:
            raise ValueError("시작 회차는 마지막 회차보다 클 수 없습니다.")
        if args.timeout == 0:
            raise ValueError("--timeout은 0보다 커야 합니다.")
        if args.max_retries < 0:
            raise ValueError("--max-retries는 0 이상이어야 합니다.")
        if args.delay > args.max_delay:
            raise ValueError("--delay는 --max-delay보다 클 수 없습니다.")
        if args.cooldown_min > args.cooldown_max:
            raise ValueError("--cooldown-min은 --cooldown-max보다 클 수 없습니다.")

        data_dir = Path(__file__).resolve().parent.parent
        output_path = (args.output or data_dir / "output" / "winning_shops.jsonl").expanduser()
        failed_path = (args.failed_output or data_dir / "output" / "failed_draws.jsonl").expanduser()
        log_path = (args.log_file or data_dir / "output" / "fetch_winning_shops.log").expanduser()
        configure_logging(log_path)

        requested = list(range(args.start_draw, end_draw + 1))
        completed = load_completed_draws(output_path)
        pending = [draw for draw in requested if draw not in completed]
        logger.info("조회 범위 %s~%s회차 | 남음 %s개 | 건너뜀 %s개",
                    args.start_draw, end_draw, len(pending), len(requested) - len(pending))

        pass_args = (
            output_path, failed_path, args.timeout, args.max_retries, args.max_backoff,
            args.delay, args.max_delay, args.timeout_streak_threshold,
            args.cooldown_min, args.cooldown_max,
        )
        failed, first_saved = collect_pass(pending, "first", *pass_args)
        retry_failed: list[int] = []
        retry_saved = 0
        if failed:
            logger.info("1차 순회 완료: 실패한 %s개 회차를 다시 처리합니다.", len(failed))
            retry_failed, retry_saved = collect_pass(failed, "retry", *pass_args)

        logger.info("완료 | 저장 %s개 | 최종 실패 %s개 | %s",
                    first_saved + retry_saved, len(retry_failed), output_path)
        if retry_failed:
            logger.warning("최종 실패 회차: %s | 실패 이력: %s", retry_failed, failed_path)
        return 0
    except KeyboardInterrupt:
        logger.warning("사용자 요청(Ctrl+C)으로 중단했습니다. 다음 실행 시 이어서 진행합니다.")
        return 130
    except (ValueError, RuntimeError, OSError) as exc:
        if logger.handlers:
            logger.error("오류: %s", exc)
        else:
            print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
