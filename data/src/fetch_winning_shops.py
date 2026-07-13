"""Download Lotto 6/45 winning-shop results and append them as JSON Lines."""

from __future__ import annotations

import json
import argparse
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://www.dhlottery.co.kr/wnprchsplcsrch/selectLtWnShp.do"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DELAY_SECONDS = 0.3
DEFAULT_MAX_RETRIES = 5
DEFAULT_MAX_BACKOFF_SECONDS = 60.0

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
    parser = argparse.ArgumentParser(
        description="회차별 로또 당첨 판매점을 JSON Lines 파일 끝에 추가합니다."
    )
    parser.add_argument("start_draw", type=positive_int, help="조회 회차 또는 시작 회차")
    parser.add_argument(
        "end_draw",
        type=positive_int,
        nargs="?",
        help="끝 회차(생략하면 시작 회차만 조회)",
    )
    parser.add_argument("--output", type=Path, help="출력 JSONL 파일 경로")
    parser.add_argument("--log-file", type=Path, help="로그 파일 경로")
    parser.add_argument(
        "--delay",
        type=non_negative_float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"회차별 요청 간격(초, 기본값: {DEFAULT_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--timeout",
        type=non_negative_float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"요청 제한 시간(초, 기본값: {DEFAULT_TIMEOUT_SECONDS:g})",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"일시적 오류의 최대 재시도 횟수(기본값: {DEFAULT_MAX_RETRIES})",
    )
    parser.add_argument(
        "--max-backoff",
        type=non_negative_float,
        default=DEFAULT_MAX_BACKOFF_SECONDS,
        help=f"재시도 최대 대기 시간(초, 기본값: {DEFAULT_MAX_BACKOFF_SECONDS:g})",
    )
    return parser.parse_args()


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    file_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
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
        return "URL_ERROR"
    if isinstance(error, ConnectionError):
        return "CONNECTION_ERROR"
    return type(error).__name__.upper()


def fetch_draw(
    draw: int,
    timeout: float,
    max_retries: int,
    max_backoff: float,
) -> dict[str, Any]:
    url = f"{API_URL}?{urlencode({'srchLtEpsd': draw})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 lottoShopScanner/1.0",
        },
    )

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
            logger.warning(
                "error_code=%s | %s회차 서버 오류. %.1f초 후 재시도 (%s/%s)",
                error_code, draw, wait, attempt, max_retries,
            )
            exc.close()
            time.sleep(wait)
        except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
            error_code = exception_error_code(exc)
            if attempt == max_attempts:
                raise RuntimeError(
                    f"error_code={error_code} | {draw}회차 조회 실패 "
                    f"({max_attempts}회 시도): {exc}"
                ) from exc
            wait = backoff_seconds(attempt, max_backoff)
            logger.warning(
                "error_code=%s | %s회차 일시적 통신 오류: %s. "
                "%.1f초 후 재시도 (%s/%s)",
                error_code, draw, exc, wait, attempt, max_retries,
            )
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
                record = json.loads(line)
                draw = record.get("draw")
                if isinstance(draw, int):
                    completed.add(draw)
                else:
                    logger.warning("출력 파일 %s번째 줄에 유효한 draw가 없습니다.", line_number)
            except json.JSONDecodeError:
                logger.warning("출력 파일 %s번째 줄이 올바른 JSON이 아니어서 무시합니다.", line_number)
    return completed


def main() -> int:
    try:
        args = parse_args()
        start_draw = args.start_draw
        end_draw = args.end_draw if args.end_draw is not None else start_draw
        if start_draw > end_draw:
            raise ValueError("시작 회차는 끝 회차보다 클 수 없습니다.")

        if args.timeout == 0:
            raise ValueError("--timeout은 0보다 커야 합니다.")
        if args.max_retries < 0:
            raise ValueError("--max-retries는 0 이상이어야 합니다.")

        data_dir = Path(__file__).resolve().parent.parent
        default_output = data_dir / "output" / "winning_shops.jsonl"
        output_path = (args.output or default_output).expanduser()
        default_log = data_dir / "output" / "fetch_winning_shops.log"
        log_path = (args.log_file or default_log).expanduser()
        configure_logging(log_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        requested_draws = list(range(start_draw, end_draw + 1))
        completed_draws = load_completed_draws(output_path)
        pending_draws = [draw for draw in requested_draws if draw not in completed_draws]
        skipped_count = len(requested_draws) - len(pending_draws)
        for draw in requested_draws:
            if draw in completed_draws:
                logger.debug("건너뜀: %s회차는 출력 파일에 이미 저장되어 있습니다.", draw)
        logger.info(
            "조회 범위 %s~%s회차 | 남은 %s개 | 건너뜀 %s개",
            start_draw, end_draw, len(pending_draws), skipped_count,
        )

        saved_count = 0
        with output_path.open("a", encoding="utf-8", newline="\n") as output_file:
            for index, draw in enumerate(pending_draws, start=1):
                logger.info("[%s/%s] %s회차 조회 중...", index, len(pending_draws), draw)
                response = fetch_draw(draw, args.timeout, args.max_retries, args.max_backoff)
                record = {"draw": draw, **response}
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                output_file.flush()
                os.fsync(output_file.fileno())
                saved_count += 1
                logger.debug(
                    "[%s/%s] %s회차 저장 완료 (%s개 판매점)",
                    index, len(pending_draws), draw, response["data"].get("total", 0),
                )

                if index < len(pending_draws) and args.delay:
                    time.sleep(args.delay)

        logger.info(
            "완료 | 저장 %s개 | 건너뜀 %s개 | %s",
            saved_count, skipped_count, output_path,
        )
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
