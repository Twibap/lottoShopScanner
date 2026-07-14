"""Load Lotto JSONL files into PostgreSQL and refresh shop ranking statistics."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from build_shop_rankings import read_jsonl


DRAW_UPSERT = """
INSERT INTO draw_results (
    draw, draw_date, first_winner_count, first_prize, first_total_prize,
    second_winner_count, second_prize, second_total_prize, raw_data, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
ON CONFLICT (draw) DO UPDATE SET
    draw_date = EXCLUDED.draw_date,
    first_winner_count = EXCLUDED.first_winner_count,
    first_prize = EXCLUDED.first_prize,
    first_total_prize = EXCLUDED.first_total_prize,
    second_winner_count = EXCLUDED.second_winner_count,
    second_prize = EXCLUDED.second_prize,
    second_total_prize = EXCLUDED.second_total_prize,
    raw_data = EXCLUDED.raw_data,
    updated_at = now()
"""

SHOP_UPSERT = """
INSERT INTO shops (
    shop_id, name, address, region, phone, latitude, longitude,
    latest_draw, raw_data, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
ON CONFLICT (shop_id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    region = EXCLUDED.region,
    phone = EXCLUDED.phone,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    latest_draw = EXCLUDED.latest_draw,
    raw_data = EXCLUDED.raw_data,
    updated_at = now()
WHERE EXCLUDED.latest_draw >= shops.latest_draw
"""

EVENT_UPSERT = """
INSERT INTO winning_events (
    draw, event_sequence, shop_id, prize_rank, prize_amount, win_method, raw_data
) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
ON CONFLICT (draw, event_sequence) DO UPDATE SET
    shop_id = EXCLUDED.shop_id,
    prize_rank = EXCLUDED.prize_rank,
    prize_amount = EXCLUDED.prize_amount,
    win_method = EXCLUDED.win_method,
    raw_data = EXCLUDED.raw_data
"""

REFRESH_STATISTICS = """
WITH aggregates AS (
    SELECT
        shop_id,
        count(*) FILTER (WHERE prize_rank = 1)::integer AS first_count,
        count(*) FILTER (WHERE prize_rank = 2)::integer AS second_count,
        coalesce(sum(prize_amount) FILTER (WHERE prize_rank = 1), 0)::bigint AS first_prize,
        coalesce(sum(prize_amount) FILTER (WHERE prize_rank = 2), 0)::bigint AS second_prize,
        sum(prize_amount)::bigint AS total_prize,
        count(DISTINCT draw)::integer AS winning_draw_count,
        max(draw)::integer AS last_winning_draw
    FROM winning_events
    GROUP BY shop_id
), ranked AS (
    SELECT
        aggregates.*,
        rank() OVER (ORDER BY first_count DESC)::integer AS first_rank,
        rank() OVER (ORDER BY second_count DESC)::integer AS second_rank,
        rank() OVER (ORDER BY total_prize DESC)::integer AS total_prize_rank
    FROM aggregates
), upserted AS (
    INSERT INTO shop_statistics (
        shop_id, first_count, second_count, first_prize, second_prize, total_prize,
        winning_draw_count, last_winning_draw, first_rank, second_rank,
        total_prize_rank, updated_at
    )
    SELECT
        shop_id, first_count, second_count, first_prize, second_prize, total_prize,
        winning_draw_count, last_winning_draw, first_rank, second_rank,
        total_prize_rank, now()
    FROM ranked
    ON CONFLICT (shop_id) DO UPDATE SET
        first_count = EXCLUDED.first_count,
        second_count = EXCLUDED.second_count,
        first_prize = EXCLUDED.first_prize,
        second_prize = EXCLUDED.second_prize,
        total_prize = EXCLUDED.total_prize,
        winning_draw_count = EXCLUDED.winning_draw_count,
        last_winning_draw = EXCLUDED.last_winning_draw,
        first_rank = EXCLUDED.first_rank,
        second_rank = EXCLUDED.second_rank,
        total_prize_rank = EXCLUDED.total_prize_rank,
        updated_at = now()
    RETURNING shop_id
)
DELETE FROM shop_statistics
WHERE shop_id NOT IN (SELECT shop_id FROM upserted)
"""


def parse_args() -> argparse.Namespace:
    app_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="수집 JSONL을 PostgreSQL에 적재하고 랭킹을 갱신합니다.")
    parser.add_argument("--shops", type=Path, default=app_dir / "output" / "winning_shops.jsonl")
    parser.add_argument("--draw-results", type=Path, default=app_dir / "output" / "draw_results.jsonl")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"),
                        help="PostgreSQL 접속 URL 또는 DATABASE_URL 환경 변수")
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args()


def require_int(record: dict[str, Any], field: str, source: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{source}: {field}는 0 이상의 정수여야 합니다.")
    return value


def draw_row(record: dict[str, Any], source: str) -> tuple[object, ...]:
    draw = require_int(record, "ltEpsd", source)
    date_text = record.get("ltRflYmd")
    if not isinstance(date_text, str):
        raise ValueError(f"{source}: ltRflYmd가 없습니다.")
    try:
        draw_date = datetime.strptime(date_text, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{source}: 잘못된 ltRflYmd입니다: {date_text!r}") from exc
    return (
        draw, draw_date,
        require_int(record, "rnk1WnNope", source),
        require_int(record, "rnk1WnAmt", source),
        require_int(record, "rnk1SumWnAmt", source),
        require_int(record, "rnk2WnNope", source),
        require_int(record, "rnk2WnAmt", source),
        require_int(record, "rnk2SumWnAmt", source),
        json.dumps(record, ensure_ascii=False),
    )


def load_prize_map(path: Path) -> tuple[list[tuple[object, ...]], dict[int, tuple[int, int]]]:
    rows: list[tuple[object, ...]] = []
    prizes: dict[int, tuple[int, int]] = {}
    for line_number, record in read_jsonl(path):
        row = draw_row(record, f"{path}:{line_number}")
        draw = row[0]
        if draw in prizes:
            raise ValueError(f"{path}:{line_number}: {draw}회차가 중복되었습니다.")
        rows.append(row)
        prizes[draw] = (row[3], row[6])
    if not rows:
        raise ValueError(f"회차 데이터가 비어 있습니다: {path}")
    return rows, prizes


def shop_and_event_rows(
    path: Path, prizes: dict[int, tuple[int, int]],
) -> Iterator[tuple[tuple[object, ...], tuple[object, ...]]]:
    seen_draws: set[int] = set()
    for line_number, record in read_jsonl(path):
        draw = record.get("draw")
        entries = record.get("data", {}).get("list") if isinstance(record.get("data"), dict) else None
        if not isinstance(draw, int) or isinstance(draw, bool) or not isinstance(entries, list):
            raise ValueError(f"{path}:{line_number}: draw와 data.list 형식이 올바르지 않습니다.")
        if draw in seen_draws:
            raise ValueError(f"{path}:{line_number}: {draw}회차가 중복되었습니다.")
        seen_draws.add(draw)
        if entries and draw not in prizes:
            raise ValueError(f"{path}:{line_number}: {draw}회차 당첨금 정보가 없습니다.")
        for position, shop in enumerate(entries, start=1):
            if not isinstance(shop, dict):
                raise ValueError(f"{path}:{line_number}: 판매점 항목이 객체가 아닙니다.")
            shop_id = shop.get("ltShpId")
            rank = shop.get("wnShpRnk")
            sequence = shop.get("rnum", position)
            if not isinstance(shop_id, str) or not shop_id:
                raise ValueError(f"{path}:{line_number}: ltShpId가 없습니다.")
            if rank not in (1, 2) or not isinstance(sequence, int) or sequence < 1:
                raise ValueError(f"{path}:{line_number}: wnShpRnk 또는 rnum이 올바르지 않습니다.")
            prize = prizes[draw][rank - 1]
            raw = json.dumps(shop, ensure_ascii=False)
            shop_row = (
                shop_id, str(shop.get("shpNm") or ""), str(shop.get("shpAddr") or ""),
                str(shop.get("region") or shop.get("tm1ShpLctnAddr") or ""),
                shop.get("shpTelno") if isinstance(shop.get("shpTelno"), str) else None,
                shop.get("shpLat") if isinstance(shop.get("shpLat"), (int, float)) else None,
                shop.get("shpLot") if isinstance(shop.get("shpLot"), (int, float)) else None,
                draw, raw,
            )
            event_row = (draw, sequence, shop_id, rank, prize, shop.get("atmtPsvYnTxt"), raw)
            yield shop_row, event_row


def batched(items: Iterable[tuple[object, ...]], size: int) -> Iterator[list[tuple[object, ...]]]:
    batch: list[tuple[object, ...]] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def load(database_url: str, shops_path: Path, draws_path: Path, batch_size: int) -> tuple[int, int]:
    if batch_size < 1:
        raise ValueError("--batch-size는 1 이상이어야 합니다.")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg가 없습니다. requirements.txt 의존성을 설치하세요.") from exc

    draw_rows, prizes = load_prize_map(draws_path)
    event_count = 0
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for batch in batched(draw_rows, batch_size):
                cursor.executemany(DRAW_UPSERT, batch)
            cursor.execute(
                "DELETE FROM winning_events WHERE draw = ANY(%s)",
                ([row[0] for row in draw_rows],),
            )
            shop_batch: list[tuple[object, ...]] = []
            event_batch: list[tuple[object, ...]] = []
            for shop_row, event_row in shop_and_event_rows(shops_path, prizes):
                shop_batch.append(shop_row)
                event_batch.append(event_row)
                event_count += 1
                if len(event_batch) == batch_size:
                    cursor.executemany(SHOP_UPSERT, shop_batch)
                    cursor.executemany(EVENT_UPSERT, event_batch)
                    shop_batch.clear()
                    event_batch.clear()
            if event_batch:
                cursor.executemany(SHOP_UPSERT, shop_batch)
                cursor.executemany(EVENT_UPSERT, event_batch)
            cursor.execute(REFRESH_STATISTICS)
    return len(draw_rows), event_count


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("오류: --database-url 또는 DATABASE_URL이 필요합니다.", file=sys.stderr)
        return 1
    try:
        draw_count, event_count = load(
            args.database_url, args.shops, args.draw_results, args.batch_size
        )
        print(f"완료 | 회차 {draw_count:,}개 | 당첨 이벤트 {event_count:,}개 | 랭킹 갱신")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
