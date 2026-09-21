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
        "minimum_fare": 75.0,
        "maximum_fare": 250.0,
    }
    data.update(changes)
    return Flight(**data)


class FlightTests(unittest.TestCase):
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

    def test_route_weekday_time_and_seat_factor_boundaries(self):
        for popularity, expected in (("Low", .95), ("Medium", 1), ("High", 1.10)):
            with self.subTest(popularity=popularity):
                self.assertEqual(calculate_price(make_flight(route_popularity=popularity), self.reference).route_factor, expected)
        self.assertEqual(calculate_price(make_flight(flight_date="2026-10-03"), self.reference).day_factor, 1.05)
        self.assertEqual(calculate_price(make_flight(flight_date="2026-10-05"), self.reference).day_factor, 1.00)
        for time, expected in (("05:59", .90), ("06:00", 1.00), ("16:59", 1.00),
                               ("17:00", 1.05), ("20:59", 1.05), ("21:00", .90)):
            with self.subTest(time=time):
                self.assertEqual(calculate_price(make_flight(departure_time=time), self.reference).time_of_day_factor, expected)
        for seats, expected in ((0, 1.25), (10, 1.25), (11, 1.10), (20, 1.10),
                                (21, 1.00), (50, 1.00), (51, .95), (100, .95)):
            with self.subTest(seats=seats):
                self.assertEqual(calculate_price(make_flight(seats_remaining=seats), self.reference).seats_factor, expected)

    def test_season_and_days_until_flight_boundaries(self):
        seasons = (("2027-01-05", 1.20), ("2027-01-06", .90), ("2027-03-31", .90),
                   ("2027-04-01", 1.00), ("2027-06-14", 1.00), ("2027-06-15", 1.10),
                   ("2027-08-31", 1.10), ("2027-09-01", 1.00),
                   ("2026-12-19", 1.00), ("2026-12-20", 1.20))
        for date, expected in seasons:
            with self.subTest(date=date):
                self.assertEqual(calculate_price(make_flight(flight_date=date), self.reference).season_factor, expected)
        for days, expected in ((0, 1.30), (3, 1.30), (4, 1.15), (14, 1.15),
                               (15, 1.00), (30, 1.00), (31, .95)):
            departure = self.reference + timedelta(days=days, hours=1)
            flight = make_flight(flight_date=departure.date().isoformat(), departure_time="13:00")
            with self.subTest(days=days):
                self.assertEqual(calculate_price(flight, self.reference).days_until_flight_factor, expected)

    def test_fare_bounds_and_invalid_inputs(self):
        cheap = make_flight(flight_date="2027-02-20", departure_time="04:00",
                            route_popularity="Low", seats_remaining=100)
        self.assertEqual(calculate_price(cheap, self.reference).price, 75.0)
        expensive = make_flight(flight_date="2026-12-20", departure_time="18:00",
                                route_popularity="High", seats_remaining=0, maximum_fare=150)
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
