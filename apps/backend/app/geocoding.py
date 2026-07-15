from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
CLIENT_ID = os.environ.get("NAVER_GEOCODE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("NAVER_GEOCODE_CLIENT_SECRET")


class GeocodingUnavailable(RuntimeError):
    pass


def geocoding_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


def search_naver_addresses(query: str, *, limit: int) -> list[dict[str, Any]]:
    if not geocoding_configured():
        return []
    url = f"{GEOCODE_URL}?{urlencode({'query': query})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "x-ncp-apigw-api-key-id": CLIENT_ID or "",
            "x-ncp-apigw-api-key": CLIENT_SECRET or "",
        },
    )
    try:
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise GeocodingUnavailable("NAVER 주소 검색에 실패했습니다.") from exc

    addresses = payload.get("addresses") if isinstance(payload, dict) else None
    if not isinstance(addresses, list):
        return []
    results: list[dict[str, Any]] = []
    for address in addresses[:limit]:
        if not isinstance(address, dict):
            continue
        try:
            latitude = float(address["y"])
            longitude = float(address["x"])
        except (KeyError, TypeError, ValueError):
            continue
        road_address = address.get("roadAddress") or address.get("jibunAddress") or query
        jibun_address = address.get("jibunAddress") or road_address
        results.append({
            "place_id": f"naver:{latitude:.7f},{longitude:.7f}",
            "title": road_address,
            "address": jibun_address,
            "latitude": latitude,
            "longitude": longitude,
            "source": "naver",
        })
    return results
