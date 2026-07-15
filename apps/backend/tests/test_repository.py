from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repository import SORT_ORDERS, nearby_query, search_places_query  # noqa: E402


class NearbyQueryTests(unittest.TestCase):
    def test_all_product_sort_modes_are_supported(self) -> None:
        self.assertEqual(
            set(SORT_ORDERS),
            {"distance", "first_wins", "second_wins", "total_prize", "recent_win"},
        )
        for sort in SORT_ORDERS:
            with self.subTest(sort=sort):
                query = nearby_query(sort)
                self.assertIn("ST_DWithin", query)
                self.assertIn("row_number() OVER", query)
                self.assertIn("s.location IS NOT NULL", query)

    def test_unknown_sort_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            nearby_query("unknown")  # type: ignore[arg-type]

    def test_place_search_uses_only_valid_locations(self) -> None:
        query = search_places_query()

        self.assertIn("s.location IS NOT NULL", query)
        self.assertIn("s.name ILIKE", query)
        self.assertIn("s.address ILIKE", query)
        self.assertIn("s.region ILIKE", query)
        self.assertIn("LIMIT %(limit)s", query)
