from __future__ import annotations

from typing import Any, Literal


SortKey = Literal["distance", "first_wins", "second_wins", "total_prize", "recent_win"]

SORT_ORDERS: dict[str, str] = {
    "distance": "distance_m ASC, name ASC, shop_id ASC",
    "first_wins": (
        "first_count DESC, second_count DESC, last_winning_draw DESC, "
        "name ASC, shop_id ASC"
    ),
    "second_wins": (
        "second_count DESC, first_count DESC, last_winning_draw DESC, "
        "name ASC, shop_id ASC"
    ),
    "total_prize": (
        "total_prize DESC, first_prize DESC, last_winning_draw DESC, "
        "name ASC, shop_id ASC"
    ),
    "recent_win": (
        "last_winning_draw DESC, first_count DESC, second_count DESC, "
        "name ASC, shop_id ASC"
    ),
}


def nearby_query(sort: SortKey) -> str:
    try:
        order_by = SORT_ORDERS[sort]
    except KeyError as exc:
        raise ValueError(f"unsupported sort: {sort}") from exc
    return f"""
WITH origin AS (
    SELECT ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography AS point
), candidates AS (
    SELECT
        s.shop_id,
        s.name,
        s.address,
        s.latitude,
        s.longitude,
        round(ST_Distance(s.location, origin.point))::integer AS distance_m,
        st.first_count,
        st.second_count,
        st.total_prize,
        st.winning_draw_count,
        st.last_winning_draw,
        st.first_rank,
        st.second_rank,
        st.total_prize_rank,
        greatest(s.updated_at, st.updated_at) AS updated_at
    FROM shops s
    JOIN shop_statistics st ON st.shop_id = s.shop_id
    CROSS JOIN origin
    WHERE s.location IS NOT NULL
      AND ST_DWithin(s.location, origin.point, %(radius_m)s)
), ranked AS (
    SELECT candidates.*, row_number() OVER (ORDER BY {order_by})::integer AS result_rank
    FROM candidates
)
SELECT * FROM ranked
WHERE result_rank > %(after_rank)s
ORDER BY result_rank
LIMIT %(fetch_limit)s
"""


def fetch_nearby(
    connection: Any, *, lat: float, lng: float, radius_m: int,
    sort: SortKey, after_rank: int, limit: int,
) -> list[dict[str, Any]]:
    params = {
        "lat": lat, "lng": lng, "radius_m": radius_m,
        "after_rank": after_rank, "fetch_limit": limit + 1,
    }
    with connection.cursor() as cursor:
        cursor.execute(nearby_query(sort), params)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def search_places_query() -> str:
    return """
WITH matches AS (
SELECT
    s.shop_id AS place_id,
    s.name AS title,
    s.address,
    s.latitude,
    s.longitude,
    'shop' AS source,
    CASE
        WHEN lower(s.name) = lower(%(query)s) THEN 0
        WHEN lower(s.name) LIKE lower(%(prefix_pattern)s) THEN 1
        WHEN lower(s.address) LIKE lower(%(prefix_pattern)s) THEN 2
        ELSE 3
    END AS match_rank
FROM shops s
WHERE s.location IS NOT NULL
  AND (
      s.name ILIKE %(pattern)s
      OR s.address ILIKE %(pattern)s
      OR s.region ILIKE %(pattern)s
  )
ORDER BY match_rank, s.latest_draw DESC, s.name ASC, s.shop_id ASC
LIMIT %(limit)s
)
SELECT place_id, title, address, latitude, longitude, source
FROM matches
"""


def search_places(connection: Any, *, query: str, limit: int) -> list[dict[str, Any]]:
    normalized = " ".join(query.strip().split())
    params = {
        "query": normalized,
        "pattern": f"%{normalized}%",
        "prefix_pattern": f"{normalized}%",
        "limit": limit,
    }
    with connection.cursor() as cursor:
        cursor.execute(search_places_query(), params)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
