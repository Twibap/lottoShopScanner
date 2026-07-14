"""Collect Lotto 6/45 draw numbers and prize data as JSON Lines."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
DEFAULT_TIMEOUT = 30.0
DEFAULT_DELAY = 1.0
DEFAULT_MAX_DELAY = 2.5
DEFAULT_MAX_RETRIES = 5
DEFAULT_MAX_BACKOFF = 60.0

logger = logging.getLogger("draw_results")


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"정수여야 합니다: {value!r}") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다: {parsed}")
    return parsed


def non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"숫자여야 합니다: {value!r}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"0 이상이어야 합니다: {parsed}")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="회차별 로또 6/45 당첨번호와 등수별 당첨금을 JSONL로 수집합니다."
    )
    parser.add_argument("start_draw", type=positive_int, help="시작 회차")
    parser.add_argument("end_draw", type=positive_int, nargs="?", help="마지막 회차")
    parser.add_argument("--output", type=Path, help="출력 JSONL 경로")
    parser.add_argument("--failed-output", type=Path, help="실패 이력 JSONL 경로")
    parser.add_argument("--log-file", type=Path, help="로그 파일 경로")
    parser.add_argument("--delay", type=non_negative_float, default=DEFAULT_DELAY,
                        help="요청 사이 최소 대기 시간(초)")
    parser.add_argument("--max-delay", type=non_negative_float, default=DEFAULT_MAX_DELAY,
                        help="요청 사이 최대 대기 시간(초)")
    parser.add_argument("--timeout", type=non_negative_float, default=DEFAULT_TIMEOUT,
                        help="요청 제한 시간(초)")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        help="요청별 최대 재시도 횟수")
    parser.add_argument("--max-backoff", type=non_negative_float, default=DEFAULT_MAX_BACKOFF,
                        help="재시도 최대 대기 시간(초)")
    return parser.parse_args()


def configure_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
    file_handler = logging.FileHandler(path, encoding="utf-8")
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


def validate_draw(draw: int, record: object) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("ltEpsd") != draw:
        raise RuntimeError(f"error_code=DRAW_NOT_FOUND | {draw}회차가 응답에 없습니다.")
    required = [
        *(f"tm{number}WnNo" for number in range(1, 7)), "bnsWnNo", "ltRflYmd",
        *(f"rnk{rank}{suffix}" for rank in range(1, 6)
          for suffix in ("WnNope", "WnAmt", "SumWnAmt")),
    ]
    missing = [field for field in required if not isinstance(record.get(field), (int, str))]
    if missing:
        raise RuntimeError(
            f"error_code=INVALID_DRAW | {draw}회차 필수 필드가 없습니다: {', '.join(missing)}"
        )
    return record


def fetch_draw(draw: int, timeout: float, max_retries: int,
               max_backoff: float) -> dict[str, Any]:
    query = urlencode({"srchDir": "center", "srchLtEpsd": draw, "_": int(time.time() * 1000)})
    request = Request(f"{API_URL}?{query}", headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 lottoShopScanner/1.0",
    })
    attempts = max_retries + 1
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                payload = json.loads(response.read().decode(charset))
            data = payload.get("data") if isinstance(payload, dict) else None
            records = data.get("list") if isinstance(data, dict) else None
            if not isinstance(records, list):
                result_code = payload.get("resultCode") if isinstance(payload, dict) else None
                code = f"API_{result_code}" if result_code is not None else "INVALID_RESPONSE"
                raise RuntimeError(f"error_code={code} | {draw}회차 응답 형식이 올바르지 않습니다.")
            record = next((item for item in records
                           if isinstance(item, dict) and item.get("ltEpsd") == draw), None)
            return validate_draw(draw, record)
        except HTTPError as exc:
            code = f"HTTP_{exc.code}"
            retryable = exc.code in (408, 429) or 500 <= exc.code < 600
            if not retryable or attempt == attempts:
                exc.close()
                raise RuntimeError(f"error_code={code} | {draw}회차 HTTP 오류: {exc.reason}") from exc
            wait = retry_after_seconds(exc)
            if wait is None:
                wait = min(max_backoff, 2 ** (attempt - 1) + random.uniform(0, 1))
            wait = min(wait, max_backoff)
            exc.close()
            logger.warning("error_code=%s | %.1f초 후 재시도 (%s/%s)",
                           code, wait, attempt, max_retries)
            time.sleep(wait)
        except (URLError, OSError, json.JSONDecodeError) as exc:
            if attempt == attempts:
                code = "INVALID_JSON" if isinstance(exc, json.JSONDecodeError) else "NETWORK_ERROR"
                raise RuntimeError(f"error_code={code} | {draw}회차 조회 실패: {exc}") from exc
            wait = min(max_backoff, 2 ** (attempt - 1) + random.uniform(0, 1))
            logger.warning("%s회차 통신 오류: %s. %.1f초 후 재시도 (%s/%s)",
                           draw, exc, wait, attempt, max_retries)
            time.sleep(wait)
    raise AssertionError("unreachable")


def load_completed_draws(path: Path) -> set[int]:
    completed: set[int] = set()
    if not path.exists():
        return completed
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                draw = json.loads(line).get("ltEpsd")
                if isinstance(draw, int):
                    completed.add(draw)
                else:
                    logger.warning("출력 파일 %s번째 줄에 유효한 ltEpsd가 없습니다.", line_number)
            except json.JSONDecodeError:
                logger.warning("출력 파일 %s번째 줄의 잘못된 JSON을 무시합니다.", line_number)
    return completed


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(record, ensure_ascii=False) + "\n")
        output.flush()
        os.fsync(output.fileno())


def error_code(error: RuntimeError) -> str:
    marker = "error_code="
    if marker not in str(error):
        return "RUNTIME_ERROR"
    return str(error).split(marker, 1)[1].split(" |", 1)[0]


def collect(draws: list[int], phase: str, output: Path, failures: Path,
            timeout: float, max_retries: int, max_backoff: float,
            delay: float, max_delay: float,
            fetcher: Callable[[int, float, int, float], dict[str, Any]] | None = None,
            ) -> tuple[list[int], int]:
    if fetcher is None:
        fetcher = fetch_draw
    failed: list[int] = []
    saved = 0
    for index, draw in enumerate(draws, start=1):
        logger.info("[%s %s/%s] %s회차 조회 중...", phase, index, len(draws), draw)
        try:
            append_jsonl(output, fetcher(draw, timeout, max_retries, max_backoff))
            saved += 1
        except RuntimeError as exc:
            failed.append(draw)
            append_jsonl(failures, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "draw": draw, "phase": phase, "error_code": error_code(exc), "message": str(exc),
            })
            logger.error("%s회차를 건너뜁니다: %s", draw, exc)
        if index < len(draws) and max_delay:
            time.sleep(random.uniform(delay, max_delay))
    return failed, saved


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

        app_dir = Path(__file__).resolve().parent.parent
        output = (args.output or app_dir / "output" / "draw_results.jsonl").expanduser()
        failures = (args.failed_output or app_dir / "output" / "failed_draw_results.jsonl").expanduser()
        log_file = (args.log_file or app_dir / "output" / "fetch_draw_results.log").expanduser()
        configure_logging(log_file)

        requested = list(range(args.start_draw, end_draw + 1))
        completed = load_completed_draws(output)
        pending = [draw for draw in requested if draw not in completed]
        logger.info("조회 범위 %s~%s회차 | 남음 %s개 | 건너뜀 %s개",
                    args.start_draw, end_draw, len(pending), len(requested) - len(pending))
        common = (output, failures, args.timeout, args.max_retries, args.max_backoff,
                  args.delay, args.max_delay)
        failed, saved = collect(pending, "first", *common)
        final_failed: list[int] = []
        if failed:
            logger.info("1차 실패 %s개 회차를 다시 처리합니다.", len(failed))
            final_failed, retry_saved = collect(failed, "retry", *common)
            saved += retry_saved
        logger.info("완료 | 저장 %s개 | 최종 실패 %s개 | %s", saved, len(final_failed), output)
        return 0
    except KeyboardInterrupt:
        logger.warning("사용자 요청으로 중단했습니다. 다음 실행에서 이어서 진행합니다.")
        return 130
    except (ValueError, RuntimeError, OSError) as exc:
        if logger.handlers:
            logger.error("오류: %s", exc)
        else:
            print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
