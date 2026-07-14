"""Audit shop coordinates before enabling location-based search."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from build_shop_rankings import read_jsonl


KOREA_LATITUDE_RANGE = (32.0, 39.0)
KOREA_LONGITUDE_RANGE = (124.0, 132.0)


def parse_args() -> argparse.Namespace:
    app_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Check shop ranking coordinates for missing, invalid, and duplicate values."
    )
    parser.add_argument(
        "--input", type=Path, default=app_dir / "output" / "shop_rankings.jsonl",
        help="shop ranking JSONL path",
    )
    parser.add_argument("--output", type=Path, help="optional JSON audit report path")
    return parser.parse_args()


def shop_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "shopId": record.get("shopId"), "name": record.get("name"),
        "address": record.get("address"), "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
    }


def valid_number(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def is_non_physical_candidate(record: dict[str, Any]) -> bool:
    searchable = " ".join(str(record.get(field) or "").lower()
                          for field in ("name", "address"))
    return "dhlottery.co.kr" in searchable


def audit(path: Path) -> dict[str, Any]:
    total = 0
    missing: list[dict[str, Any]] = []
    non_numeric: list[dict[str, Any]] = []
    zero: list[dict[str, Any]] = []
    outside_korea: list[dict[str, Any]] = []
    non_physical: list[dict[str, Any]] = []
    coordinate_shops: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)

    for _, record in read_jsonl(path):
        total += 1
        latitude = record.get("latitude")
        longitude = record.get("longitude")
        summary = shop_summary(record)
        if is_non_physical_candidate(record):
            non_physical.append(summary)
        if latitude is None or longitude is None:
            missing.append(summary)
            continue
        if not valid_number(latitude) or not valid_number(longitude):
            non_numeric.append(summary)
            continue

        latitude = float(latitude)
        longitude = float(longitude)
        coordinate_shops[(latitude, longitude)].append(summary)
        if latitude == 0.0 and longitude == 0.0:
            zero.append(summary)
        elif not (KOREA_LATITUDE_RANGE[0] <= latitude <= KOREA_LATITUDE_RANGE[1]
                  and KOREA_LONGITUDE_RANGE[0] <= longitude <= KOREA_LONGITUDE_RANGE[1]):
            outside_korea.append(summary)

    duplicate_groups = [
        {"latitude": coordinate[0], "longitude": coordinate[1], "shops": shops}
        for coordinate, shops in coordinate_shops.items() if len(shops) > 1
    ]
    duplicate_groups.sort(
        key=lambda group: (-len(group["shops"]), group["latitude"], group["longitude"])
    )
    critical_count = len(missing) + len(non_numeric) + len(zero) + len(outside_korea)
    return {
        "source": str(path),
        "bounds": {"latitude": list(KOREA_LATITUDE_RANGE),
                   "longitude": list(KOREA_LONGITUDE_RANGE)},
        "summary": {
            "totalShops": total, "validCoordinateShops": total - critical_count,
            "missingCoordinates": len(missing), "nonNumericCoordinates": len(non_numeric),
            "zeroCoordinates": len(zero), "outsideKoreaBounds": len(outside_korea),
            "duplicateCoordinateGroups": len(duplicate_groups),
            "shopsInDuplicateGroups": sum(len(group["shops"]) for group in duplicate_groups),
            "nonPhysicalCandidates": len(non_physical),
            "criticalIssues": critical_count,
        },
        "issues": {
            "missingCoordinates": missing, "nonNumericCoordinates": non_numeric,
            "zeroCoordinates": zero, "outsideKoreaBounds": outside_korea,
            "duplicateCoordinates": duplicate_groups,
            "nonPhysicalCandidates": non_physical,
        },
    }


def main() -> int:
    args = parse_args()
    try:
        report = audit(args.input)
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 1 if report["summary"]["criticalIssues"] else 0
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
