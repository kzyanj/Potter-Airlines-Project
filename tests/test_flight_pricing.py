"""Flight validation and business-rule pricing tests."""

import math
import unittest
from datetime import datetime, timedelta

from backend.flight import Flight
from backend.pricing import calculate_price


def make_flight(**changes):
    data = {
        "flight_id": "PA-TEST",
        "origin": "Toronto",
        "destination": "Montreal",
        "flight_date": "2026-10-02",
        "departure_time": "12:00",
        "route_popularity": "Medium",
        "seat_capacity": 100,
        "seats_remaining": 40,
        "base_fare": 100.0,
        "minimum_fare": 80.0,
        "maximum_fare": 250.0,
    }
    data.update(changes)
    return Flight(**data)


class FlightTests(unittest.TestCase):
    def test_seat_counts_require_integers(self):
        for field in ("seat_capacity", "seats_remaining"):
            for value in (1.5, 100.0, True, False, "100", None, math.nan, math.inf):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, "must be an integer"):
                        make_flight(**{field: value})
        for remaining in (0, 100):
            self.assertEqual(make_flight(seats_remaining=remaining).seats_remaining, remaining)

    def test_fares_require_finite_numbers(self):
        for field in ("minimum_fare", "base_fare", "maximum_fare"):
            for value in (math.nan, math.inf, -math.inf, True, False, "100", None, 10**400):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, "finite number"):
                        make_flight(**{field: value})
        flight = make_flight(minimum_fare=0, base_fare=100, maximum_fare=250)
        self.assertEqual(flight.base_fare, 100)

    def test_database_row_and_computed_properties(self):
        flight = make_flight()
        self.assertEqual(Flight.from_row(tuple(vars(flight).values())), flight)
        self.assertEqual(flight.departure, datetime(2026, 10, 2, 12))
        self.assertEqual(flight.seat_fraction, 0.4)
        with self.assertRaisesRegex(ValueError, "missing"):
            Flight.from_row(None)
        with self.assertRaisesRegex(ValueError, "11 columns"):
            Flight.from_row(("too short",))

    def test_invalid_flight_fields(self):
        invalid_cases = (
            ({"flight_id": ""}, "required"),
            ({"destination": "Toronto"}, "must differ"),
            ({"flight_date": "2026-02-30"}, "day"),
            ({"flight_date": "2026-1-02"}, "YYYY-MM-DD"),
            ({"departure_time": "6:00"}, "HH:MM"),
            ({"route_popularity": "Unknown"}, "popularity"),
            ({"seat_capacity": 0}, "Seats"),
            ({"seats_remaining": -1}, "Seats"),
            ({"seats_remaining": 101}, "Seats"),
            ({"minimum_fare": 110}, "Fare bounds"),
            ({"maximum_fare": 90}, "Fare bounds"),
        )
        for changes, message in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, message):
                    make_flight(**changes)


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.reference = datetime(2026, 9, 20, 12)

    def test_route_and_seat_factor_boundaries(self):
        for popularity, expected in (("Low", .97), ("Medium", 1), ("High", 1.06)):
            with self.subTest(popularity=popularity):
                self.assertEqual(calculate_price(make_flight(route_popularity=popularity), self.reference).route_factor, expected)
        for seats, expected in ((1, 1.30), (5, 1.30), (6, 1.22), (10, 1.22),
                                (11, 1.15), (20, 1.15), (21, 1.05), (40, 1.05),
                                (41, .97), (65, .97), (66, .92), (100, .92)):
            with self.subTest(seats=seats):
                self.assertEqual(calculate_price(make_flight(seats_remaining=seats), self.reference).seats_factor, expected)
        for seats, expected in ((1, 1.30), (11, 1.22), (21, 1.15),
                                (41, 1.05), (81, .97), (131, .92)):
            with self.subTest(fraction=seats / 200):
                self.assertEqual(calculate_price(make_flight(seat_capacity=200, seats_remaining=seats), self.reference).seats_factor, expected)
        with self.assertRaisesRegex(ValueError, "No ticket available"):
            calculate_price(make_flight(seats_remaining=0), self.reference)

    def test_only_four_factors_determine_price(self):
        # Weekday/weekend and morning/evening have no separate multipliers.
        for date in ("2026-10-02", "2026-10-03"):
            for time in ("05:59", "06:00", "17:00", "21:00"):
                result = calculate_price(make_flight(flight_date=date, departure_time=time), self.reference)
                self.assertEqual(result.price, 120.75)  # 100 × 1 × 1.05 × 1 × 1.15

    def test_season_and_days_until_flight_boundaries(self):
        seasons = (("2027-01-05", 1.25), ("2027-01-06", .90), ("2027-03-31", .90),
                   ("2027-04-01", 1.00), ("2027-06-24", 1.00), ("2027-06-25", 1.12),
                   ("2027-08-31", 1.12), ("2027-09-01", 1.00),
                   ("2026-10-31", 1.00), ("2026-11-01", .90),
                   ("2026-12-19", .90), ("2026-12-20", 1.25))
        for date, expected in seasons:
            with self.subTest(date=date):
                self.assertEqual(calculate_price(make_flight(flight_date=date), self.reference).season_factor, expected)
        for days, expected in ((0, 1.30), (3, 1.30), (4, 1.15), (14, 1.15),
                               (15, 1.05), (30, 1.05), (31, 1.00), (60, 1.00), (61, .95)):
            departure = self.reference + timedelta(days=days, hours=1)
            flight = make_flight(flight_date=departure.date().isoformat(), departure_time="13:00")
            with self.subTest(days=days):
                self.assertEqual(calculate_price(flight, self.reference).days_until_flight_factor, expected)

    def test_fare_bounds_and_invalid_inputs(self):
        cheap = make_flight(flight_date="2027-02-20", departure_time="04:00",
                            route_popularity="Low", seats_remaining=100, minimum_fare=80)
        self.assertEqual(calculate_price(cheap, self.reference).price, 80.0)
        expensive = make_flight(flight_date="2026-12-20", departure_time="18:00",
                                route_popularity="High", seats_remaining=1, maximum_fare=150)
        self.assertEqual(calculate_price(expensive, datetime(2026, 12, 19)).price, 150.0)
        with self.assertRaisesRegex(ValueError, "departed"):
            calculate_price(make_flight(), datetime(2026, 10, 3))
        nonfinite = make_flight()
        object.__setattr__(nonfinite, "base_fare", math.nan)
        with self.assertRaisesRegex(ValueError, "finite"):
            calculate_price(nonfinite, self.reference)

    def test_default_uses_system_time(self):
        departure = datetime.now() + timedelta(days=2)
        flight = make_flight(flight_date=departure.date().isoformat(),
                             departure_time=departure.strftime("%H:%M"))
        self.assertGreater(calculate_price(flight).price, 0)


if __name__ == "__main__":
    unittest.main()
