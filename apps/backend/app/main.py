from __future__ import annotations

import os
from collections.abc import Generator
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from .cursor import decode_cursor, encode_cursor
from .repository import fetch_nearby


DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://lotto:lotto-local-password@localhost:5432/lotto"
)

app = FastAPI(title="Lotto Shop Scanner API", version="0.1.0")


def database_connection() -> Generator[psycopg.Connection, None, None]:
    with psycopg.connect(DATABASE_URL) as connection:
        yield connection


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/shops/nearby")
def nearby_shops(
    lat: Annotated[float, Query(ge=32, le=39)],
    lng: Annotated[float, Query(ge=124, le=132)],
    radius_m: Annotated[int, Query(ge=0, le=10_000)] = 3_000,
    sort: Literal["distance", "first_wins", "second_wins", "total_prize", "recent_win"] = "distance",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: str | None = None,
    connection: psycopg.Connection = Depends(database_connection),
) -> dict[str, object]:
    try:
        after_rank = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="유효하지 않은 cursor입니다.") from exc
    rows = fetch_nearby(
        connection, lat=lat, lng=lng, radius_m=radius_m,
        sort=sort, after_rank=after_rank, limit=limit,
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1]["result_rank"]) if has_more and items else None
    return {
        "items": items,
        "nextCursor": next_cursor,
        "search": {"lat": lat, "lng": lng, "radiusM": radius_m, "sort": sort},
    }
