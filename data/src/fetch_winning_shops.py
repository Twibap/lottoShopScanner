"""Download Lotto 6/45 winning-shop results and append them as JSON Lines."""

from __future__ import annotations

import json
import argparse
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://www.dhlottery.co.kr/wnprchsplcsrch/selectLtWnShp.do"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DELAY_SECONDS = 0.3
MAX_ATTEMPTS = 3


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
    parser.add_argument("start_draw", type=positive_int, help="시작 회차(포함)")
    parser.add_argument("end_draw", type=positive_int, help="끝 회차(포함)")
    parser.add_argument("--output", type=Path, help="출력 JSONL 파일 경로")
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
    return parser.parse_args()


def fetch_draw(draw: int, timeout: float) -> dict[str, Any]:
    url = f"{API_URL}?{urlencode({'srchLtEpsd': draw})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 lottoShopScanner/1.0",
        },
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                payload = json.loads(response.read().decode(charset))

            if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
                raise RuntimeError(f"{draw}회차 응답 형식이 예상과 다릅니다.")
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    f"{draw}회차 조회 실패 ({MAX_ATTEMPTS}회 시도): {exc}"
                ) from exc
            time.sleep(attempt)

    raise AssertionError("unreachable")


def main() -> int:
    try:
        args = parse_args()
        start_draw = args.start_draw
        end_draw = args.end_draw
        if start_draw > end_draw:
            raise ValueError("시작 회차는 끝 회차보다 클 수 없습니다.")

        if args.timeout == 0:
            raise ValueError("--timeout은 0보다 커야 합니다.")

        data_dir = Path(__file__).resolve().parent.parent
        default_output = data_dir / "output" / "winning_shops.jsonl"
        output_path = (args.output or default_output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        saved_count = 0
        with output_path.open("a", encoding="utf-8", newline="\n") as output_file:
            for draw in range(start_draw, end_draw + 1):
                print(f"{draw}회차 조회 중...", file=sys.stderr)
                response = fetch_draw(draw, args.timeout)
                record = {"draw": draw, **response}
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                output_file.flush()
                saved_count += 1

                if draw < end_draw and args.delay:
                    time.sleep(args.delay)

        print(f"추가 저장 완료: {output_path} ({saved_count}개 회차)")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
