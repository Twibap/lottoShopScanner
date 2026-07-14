"""Build Lotto 6/45 shop rankings from winning-shop and draw-result JSONL files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, TextIO


@dataclass
class ShopStats:
    shop_id: str
    name: str = ""
    address: str = ""
    region: str = ""
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    latest_draw: int = 0
    first_count: int = 0
    second_count: int = 0
    total_prize: int = 0
    first_prize: int = 0
    second_prize: int = 0
    winning_draws: set[int] = field(default_factory=set)


def parse_args() -> argparse.Namespace:
    app_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="당첨 판매점과 회차별 당첨금을 결합하여 판매점 랭킹 JSONL을 만듭니다."
    )
    parser.add_argument(
        "--shops", type=Path, default=app_dir / "output" / "winning_shops.jsonl",
        help="당첨 판매점 JSONL 경로",
    )
    parser.add_argument(
        "--draw-results", type=Path, default=app_dir / "output" / "draw_results.jsonl",
        help="회차별 추첨 결과 및 당첨금 JSONL 경로",
    )
    parser.add_argument(
        "--output", type=Path, default=app_dir / "output" / "shop_rankings.jsonl",
        help="판매점 랭킹 JSONL 경로",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    try:
        source: TextIO = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"파일을 열 수 없습니다: {path}: {exc}") from exc
    with source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: 올바르지 않은 JSON입니다: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: JSON 객체여야 합니다.")
            yield line_number, record


def load_prizes(path: Path) -> dict[int, tuple[int, int]]:
    prizes: dict[int, tuple[int, int]] = {}
    for line_number, record in read_jsonl(path):
        draw = record.get("ltEpsd")
        first = record.get("rnk1WnAmt")
        second = record.get("rnk2WnAmt")
        if not all(isinstance(value, int) and value >= 0 for value in (draw, first, second)):
            raise ValueError(
                f"{path}:{line_number}: ltEpsd, rnk1WnAmt, rnk2WnAmt는 0 이상의 정수여야 합니다."
            )
        if draw in prizes:
            raise ValueError(f"{path}:{line_number}: {draw}회차가 중복되었습니다.")
        prizes[draw] = (first, second)
    if not prizes:
        raise ValueError(f"당첨금 데이터가 비어 있습니다: {path}")
    return prizes


def update_shop_info(stats: ShopStats, shop: dict[str, Any], draw: int) -> None:
    if draw < stats.latest_draw:
        return
    stats.name = str(shop.get("shpNm") or "")
    stats.address = str(shop.get("shpAddr") or "")
    stats.region = str(shop.get("region") or shop.get("tm1ShpLctnAddr") or "")
    stats.phone = shop.get("shpTelno") if isinstance(shop.get("shpTelno"), str) else None
    stats.latitude = shop.get("shpLat") if isinstance(shop.get("shpLat"), (int, float)) else None
    stats.longitude = shop.get("shpLot") if isinstance(shop.get("shpLot"), (int, float)) else None
    stats.latest_draw = draw


def aggregate_shops(path: Path, prizes: dict[int, tuple[int, int]]) -> dict[str, ShopStats]:
    shops: dict[str, ShopStats] = {}
    seen_draws: set[int] = set()
    for line_number, record in read_jsonl(path):
        draw = record.get("draw")
        data = record.get("data")
        entries = data.get("list") if isinstance(data, dict) else None
        if not isinstance(draw, int) or not isinstance(entries, list):
            raise ValueError(f"{path}:{line_number}: draw와 data.list 형식이 올바르지 않습니다.")
        if draw in seen_draws:
            raise ValueError(f"{path}:{line_number}: {draw}회차가 중복되었습니다.")
        seen_draws.add(draw)
        if entries and draw not in prizes:
            raise ValueError(f"{path}:{line_number}: {draw}회차 당첨금 정보가 없습니다.")
        first_prize, second_prize = prizes.get(draw, (0, 0))
        for index, shop in enumerate(entries, start=1):
            if not isinstance(shop, dict):
                raise ValueError(f"{path}:{line_number}: 판매점 {index}번 항목이 객체가 아닙니다.")
            shop_id = shop.get("ltShpId")
            rank = shop.get("wnShpRnk")
            if not isinstance(shop_id, str) or not shop_id:
                raise ValueError(f"{path}:{line_number}: 판매점 {index}번의 ltShpId가 없습니다.")
            if rank not in (1, 2):
                raise ValueError(f"{path}:{line_number}: 판매점 {index}번의 wnShpRnk가 1 또는 2가 아닙니다.")
            stats = shops.setdefault(shop_id, ShopStats(shop_id=shop_id))
            update_shop_info(stats, shop, draw)
            stats.winning_draws.add(draw)
            if rank == 1:
                stats.first_count += 1
                stats.first_prize += first_prize
                stats.total_prize += first_prize
            else:
                stats.second_count += 1
                stats.second_prize += second_prize
                stats.total_prize += second_prize
    return shops


def competition_ranks(stats: Iterable[ShopStats], attribute: str) -> dict[str, int]:
    ordered = sorted(stats, key=lambda item: (-getattr(item, attribute), item.shop_id))
    result: dict[str, int] = {}
    previous_value: int | None = None
    current_rank = 0
    for position, item in enumerate(ordered, start=1):
        value = getattr(item, attribute)
        if value != previous_value:
            current_rank = position
            previous_value = value
        result[item.shop_id] = current_rank
    return result


def ranking_records(shops: dict[str, ShopStats]) -> list[dict[str, Any]]:
    first_ranks = competition_ranks(shops.values(), "first_count")
    second_ranks = competition_ranks(shops.values(), "second_count")
    prize_ranks = competition_ranks(shops.values(), "total_prize")
    records: list[dict[str, Any]] = []
    for stats in sorted(shops.values(), key=lambda item: (-item.total_prize, item.shop_id)):
        records.append({
            "shopId": stats.shop_id,
            "name": stats.name,
            "address": stats.address,
            "region": stats.region,
            "phone": stats.phone,
            "latitude": stats.latitude,
            "longitude": stats.longitude,
            "latestDraw": stats.latest_draw,
            "winningDrawCount": len(stats.winning_draws),
            "firstCount": stats.first_count,
            "secondCount": stats.second_count,
            "firstPrize": stats.first_prize,
            "secondPrize": stats.second_prize,
            "totalPrize": stats.total_prize,
            "firstRank": first_ranks[stats.shop_id],
            "secondRank": second_ranks[stats.shop_id],
            "totalPrizeRank": prize_ranks[stats.shop_id],
        })
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            for record in records:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return count


def build_rankings(shops_path: Path, draws_path: Path, output_path: Path) -> int:
    prizes = load_prizes(draws_path)
    shops = aggregate_shops(shops_path, prizes)
    if not shops:
        raise ValueError(f"집계할 당첨 판매점이 없습니다: {shops_path}")
    return write_jsonl(output_path, ranking_records(shops))


def main() -> int:
    args = parse_args()
    try:
        count = build_rankings(args.shops, args.draw_results, args.output)
        print(f"완료 | 판매점 {count:,}개 | {args.output}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
