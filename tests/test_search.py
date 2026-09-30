"""Filter choices, flight ranking, and vectorized fare tests."""

import math
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from backend.flight import Flight
from backend.pricing import calculate_price
from backend.search import analyze_fares, get_destinations, get_flight_dates, get_origins, search_flights
from database import db


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DATABASE_PATH
        db.DATABASE_PATH = Path(self.temp_dir.name) / "search.db"
        connection = sqlite3.connect(db.DATABASE_PATH)
        try:
            connection.executescript((Path(__file__).resolve().parents[1] / "database" / "schema.sql").read_text())
        finally:
            connection.close()
        self.as_of = datetime(2026, 10, 1, 12)
        self.add_flight("PA-A", "Toronto", "Montreal", "2026-10-02", "06:00", 60)
        self.add_flight("PA-B", "Toronto", "Montreal", "2026-10-02", "18:00", 20)
        self.add_flight("PA-SOLD", "Toronto", "Montreal", "2026-10-02", "21:00", 0)
        self.add_flight("PA-PAST", "Toronto", "Montreal", "2026-09-01", "12:00", 60)
        self.add_flight("PA-OTTAWA", "Toronto", "Ottawa", "2026-10-03", "09:00", 60)
        self.add_flight("PA-RETURN", "Montreal", "Toronto", "2026-10-03", "09:00", 60)

    def tearDown(self):
        db.DATABASE_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def add_flight(self, flight_id, origin, destination, date, time, seats):
        db.insert_flight({
            "flight_id": flight_id, "origin": origin, "destination": destination,
            "flight_date": date, "departure_time": time, "route_popularity": "High",
            "seat_capacity": 100, "seats_remaining": seats,
            "base_fare": 100.0, "minimum_fare": 80.0, "maximum_fare": 250.0,
        })

    def test_filter_choices_follow_route_date_and_availability(self):
        """Build filter choices from future flights and return empty lists for unknown routes.
        Keep dates with sold-out future flights; remove a date when its last flight reaches departure."""
        self.assertEqual(get_origins(self.as_of), ["Montreal", "Toronto"])
        self.assertEqual(get_destinations("Toronto", self.as_of), ["Montreal", "Ottawa"])
        self.assertEqual(get_flight_dates("Toronto", "Montreal", self.as_of), ["2026-10-02"])
        self.assertEqual(get_destinations("Unknown", self.as_of), [])
        self.assertEqual(get_flight_dates("Toronto", "Unknown", self.as_of), [])
        after_departure = datetime(2026, 10, 2, 19)
        self.assertEqual(get_flight_dates("Toronto", "Montreal", after_departure), ["2026-10-02"])
        self.assertEqual(get_flight_dates("Toronto", "Montreal", datetime(2026, 10, 2, 21)), [])

    def test_search_includes_sold_out_excludes_departed_and_ranks_fares(self):
        """Exclude departed flights, sort available fares ascending, and place sold-out flights last with None.
        Compare individual pricing, handle unknown destinations, and trim surrounding city whitespace."""
        results = search_flights("Toronto", "Montreal", "2026-10-02", self.as_of)
        self.assertEqual([flight.flight_id for flight, _ in results], ["PA-A", "PA-B", "PA-SOLD"])
        self.assertLess(results[0][1], results[1][1])
        self.assertEqual([price for _, price in results if price is not None],
                         [calculate_price(flight, self.as_of).price for flight, price in results if price is not None])
        self.assertIsNone(results[-1][1])
        self.assertEqual(results[-1][0].seats_remaining, 0)
        self.assertEqual([flight.flight_id for flight, _ in search_flights(
            "Toronto", "Montreal", "2026-10-02", datetime(2026, 10, 2, 10)
        )], ["PA-B", "PA-SOLD"])
        self.assertEqual(search_flights("Toronto", "Unknown", "2026-10-02", self.as_of), [])
        self.assertEqual(len(search_flights(" Toronto ", " Montreal ", "2026-10-02", self.as_of)), 3)

    def test_sold_out_only_route_is_searchable(self):
        """Keep cities, dates, and results available when a route has only a sold-out flight.
        Represent its fare as None rather than incorrectly treating it as a zero-price ticket."""
        self.add_flight("PA-ONLY-SOLD", "Vancouver", "Calgary", "2026-10-04", "09:00", 0)
        self.assertIn("Vancouver", get_origins(self.as_of))
        self.assertEqual(get_destinations("Vancouver", self.as_of), ["Calgary"])
        self.assertEqual(get_flight_dates("Vancouver", "Calgary", self.as_of), ["2026-10-04"])
        results = search_flights("Vancouver", "Calgary", "2026-10-04", self.as_of)
        self.assertEqual([(flight.flight_id, price) for flight, price in results],
                         [("PA-ONLY-SOLD", None)])

    def test_search_rejects_invalid_filters(self):
        """Reject missing or blank cities, identical endpoints, invalid dates, and an invalid as_of type.
        Each invalid filter combination must raise ValueError before querying."""
        invalid_filters = (
            (None, "Montreal", "2026-10-02", self.as_of),
            ("Toronto", None, "2026-10-02", self.as_of),
            ("  ", "Montreal", "2026-10-02", self.as_of),
            ("Toronto", "Toronto", "2026-10-02", self.as_of),
            ("Toronto", "Montreal", None, self.as_of),
            ("Toronto", "Montreal", "not-a-date", self.as_of),
            ("Toronto", "Montreal", "2026-1-02", self.as_of),
            ("Toronto", "Montreal", "2026-10-02", "not-a-datetime"),
        )
        for filters in invalid_filters:
            with self.subTest(filters=filters):
                with self.assertRaises(ValueError):
                    search_flights(*filters)

    def test_vectorized_pricing_across_factor_boundaries(self):
        """Compare bulk and individual pricing across 441 season, seat, popularity, and booking-day scenarios.
        Reject a batch containing a sold-out flight; agreement alone is not independent proof of the rules."""
        from test_flight_pricing import make_flight

        flights = []
        for date in ("2027-01-05", "2027-01-06", "2027-03-31", "2027-04-01",
                     "2027-06-24", "2027-06-25", "2027-08-31", "2027-09-01",
                     "2027-10-31", "2027-11-01", "2027-12-19", "2027-12-20"):
            for seats in (1, 10, 11, 20, 21, 40, 41, 80, 81, 130, 131, 200):
                for popularity in ("Low", "Medium", "High"):
                    flights.append(make_flight(flight_date=date, seat_capacity=200,
                                               seats_remaining=seats, route_popularity=popularity,
                                               minimum_fare=0, maximum_fare=1000))
        for days in (0, 3, 4, 14, 15, 30, 31, 60, 61):
            departure = self.as_of + timedelta(days=days, hours=1)
            flights.append(make_flight(flight_date=departure.date().isoformat(), departure_time="13:00"))
        np.testing.assert_array_equal(analyze_fares(flights, self.as_of),
                                      [calculate_price(f, self.as_of).price for f in flights])
        with self.assertRaisesRegex(ValueError, "No ticket available"):
            analyze_fares([flights[0], make_flight(seats_remaining=0)], self.as_of)

    def test_vectorized_fares_enforce_both_price_limits(self):
        """Force excessive discounts and increases so bulk fares must clamp to 80 and 150.
        Compare individual pricing to verify both paths apply the same limits."""
        from test_flight_pricing import make_flight

        # Strong discounts trigger the standard 80%-of-base minimum.
        flights = [
            make_flight(flight_date="2027-02-20", route_popularity="Low",
                        seats_remaining=100, minimum_fare=80),
            make_flight(flight_date="2026-12-20", route_popularity="High",
                        seats_remaining=1, maximum_fare=150),
        ]
        as_of = datetime(2026, 12, 19)
        np.testing.assert_array_equal(analyze_fares(flights, as_of), [80.0, 150.0])
        self.assertEqual([calculate_price(f, as_of).price for f in flights], [80.0, 150.0])

    def test_vectorized_fares_match_individual_prices_and_check_inputs(self):
        """Match bulk prices against individual prices for available search results.
        Return an empty array for empty input; reject departed flights and a maximum fare corrupted to NaN."""
        results = search_flights("Toronto", "Montreal", "2026-10-02", self.as_of)
        flights = [flight for flight, price in results if price is not None]
        fares = analyze_fares(flights, self.as_of)
        np.testing.assert_array_equal(fares, [calculate_price(f, self.as_of).price for f in flights])
        self.assertEqual(analyze_fares([], self.as_of).size, 0)
        with self.assertRaisesRegex(ValueError, "departed"):
            analyze_fares(flights, datetime(2026, 10, 3))
        bad = Flight(**vars(flights[0]))
        object.__setattr__(bad, "maximum_fare", math.nan)
        with self.assertRaisesRegex(ValueError, "finite"):
            analyze_fares([bad], self.as_of)


if __name__ == "__main__":
    unittest.main()
