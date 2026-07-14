from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repository import SORT_ORDERS, nearby_query  # noqa: E402


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
