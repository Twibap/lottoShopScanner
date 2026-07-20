from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main  # noqa: E402


class PlaceSearchEndpointTests(unittest.TestCase):
    def test_external_geocoding_results_are_merged_before_shop_results(self) -> None:
        external = [{
            "place_id": "naver:37.5665000,126.9780000",
            "title": "서울특별시 중구 세종대로 110",
            "address": "서울특별시 중구 태평로1가 31",
            "latitude": 37.5665,
            "longitude": 126.978,
            "source": "naver",
        }]
        shops = [{
            "place_id": "11100928",
            "title": "신간판",
            "address": "서울 중구 무교로 24",
            "latitude": 37.5681,
            "longitude": 126.97947,
            "source": "shop",
        }]

        with (
            patch.object(main, "search_naver_addresses", return_value=external) as naver,
            patch.object(main, "search_places", return_value=shops) as shop_search,
        ):
            response = main.place_search(q="서울시청", limit=2, connection=object())

        self.assertEqual(response["items"], [*external, *shops])
        naver.assert_called_once_with("서울시청", limit=2)
        shop_search.assert_called_once()
        self.assertEqual(shop_search.call_args.kwargs["limit"], 1)


class HealthEndpointTests(unittest.TestCase):
    def test_readiness_is_ok_when_database_responds(self) -> None:
        response = main.Response()
        connection = MagicMock()
        connection.__enter__.return_value = connection

        with patch.object(main.psycopg, "connect", return_value=connection) as connect:
            body = main.readiness(response)

        self.assertEqual(body, {"status": "ok"})
        self.assertEqual(response.status_code, 200)
        connect.assert_called_once_with(main.DATABASE_URL, connect_timeout=3)
        connection.execute.assert_called_once_with("SELECT 1")

    def test_readiness_is_unavailable_when_database_fails(self) -> None:
        response = main.Response()

        with patch.object(
            main.psycopg, "connect", side_effect=main.psycopg.OperationalError("down")
        ):
            body = main.readiness(response)

        self.assertEqual(body, {"status": "unavailable"})
        self.assertEqual(response.status_code, 503)


class ShopDetailEndpointTests(unittest.TestCase):
    def test_nearby_route_is_registered_before_dynamic_shop_detail(self) -> None:
        paths = [getattr(route, "path", "") for route in main.app.routes]

        self.assertLess(
            paths.index("/v1/shops/nearby"),
            paths.index("/v1/shops/{shop_id}"),
        )

    def test_rejects_partial_coordinate_context(self) -> None:
        with self.assertRaises(main.HTTPException) as context:
            main.shop_detail(shop_id="shop-1", lat=37.5, connection=object())

        self.assertEqual(context.exception.status_code, 400)

    def test_missing_shop_returns_404(self) -> None:
        with patch.object(main, "fetch_shop_detail", return_value=None):
            with self.assertRaises(main.HTTPException) as context:
                main.shop_detail(shop_id="missing", connection=object())

        self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
