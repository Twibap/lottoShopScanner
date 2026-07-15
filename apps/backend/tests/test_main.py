from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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


if __name__ == "__main__":
    unittest.main()
