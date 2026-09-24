"""Run a small end-to-end Potter Airlines backend demonstration.

Example:
    python -m backend.cli --origin Toronto --destination Montreal \
        --date 2026-10-02 --as-of 2026-09-20 --demo-pricing --demo-crud
"""

import argparse
import sqlite3
import sys
from uuid import uuid4
from datetime import datetime, timedelta

import numpy as np

from database.db import delete_flight, get_flight_by_id, update_seats
from .admin import add_flight
from .flight import Flight
from .pricing import calculate_price
from .search import search_flights


def show_pricing_demo(flight):
    """Compare the same flight at five simulated search dates."""
    print(f"\nSimulated fare calculation for {flight.flight_id} (base {flight.base_fare:.2f}, "
          f"minimum {flight.minimum_fare:.2f}, maximum {flight.maximum_fare:.2f}):")
    for days_before in (90, 45, 20, 7, 1):
        simulated_time = flight.departure - timedelta(days=days_before)
        result = calculate_price(flight, simulated_time)
        print(
            f"  {simulated_time.date()} ({days_before} {'day' if days_before == 1 else 'days'} before): "
            f"{flight.base_fare:.2f} × route {result.route_factor:.2f} "
            f"× seats {result.seats_factor:.2f} "
            f"× season {result.season_factor:.2f} "
            f"× days {result.days_until_flight_factor:.2f} "
            f"→ fare {result.price:.2f}"
        )


def show_fare_limits_demo():
    """Use fixed in-memory scenarios to demonstrate both fare limits."""
    print("\nFare limits demonstration (fixed examples; no database changes):")
    for label, date, days, popularity, seats in (
        ("Minimum", "2027-02-20", 90, "Low", 100),
        ("Maximum", "2026-12-20", 1, "High", 1),
    ):
        flight = Flight(
            flight_id=f"DEMO-{label.upper()}", origin="Toronto", destination="Montreal",
            flight_date=date, departure_time="12:00", route_popularity=popularity,
            seat_capacity=100, seats_remaining=seats, base_fare=100.0,
            minimum_fare=80.0, maximum_fare=150.0,
        )
        result = calculate_price(flight, flight.departure - timedelta(days=days))
        raw = flight.base_fare * result.route_factor
        raw *= result.seats_factor * result.season_factor * result.days_until_flight_factor
        limit = flight.minimum_fare if label == "Minimum" else flight.maximum_fare
        assert raw < limit if label == "Minimum" else raw > limit
        assert result.price == limit
        print(f"  {label} example: departure {date}, {days} days before, "
              f"{popularity} popularity, seats {seats}/100")
        print(f"  100.00 × route {result.route_factor:.2f} "
              f"× seats {result.seats_factor:.2f} × season {result.season_factor:.2f} "
              f"× days {result.days_until_flight_factor:.2f}")
        print(f"  Calculated fare: {raw:.2f} → {label} fare applied: {result.price:.2f}")


def show_database_demo(as_of):
    """Demonstrate CRUD and a seat-price boundary using a temporary flight."""
    departure = as_of + timedelta(days=45)
    flight = add_flight({
        "flight_id": f"DEMO-{uuid4().hex}",
        "origin": "Toronto", "destination": "Montreal",
        "flight_date": departure.date().isoformat(),
        "departure_time": departure.strftime("%H:%M"),
        "route_popularity": "Medium", "seat_capacity": 100,
        "seats_remaining": 21, "base_fare": 100.0, "maximum_fare": 500.0,
    })
    try:
        print(f"INSERT: temporary flight {flight.flight_id}")
        stored = Flight.from_row(get_flight_by_id(flight.flight_id))
        before = calculate_price(stored, as_of)
        print(f"SELECT: seats {stored.seats_remaining}/100, fare {before.price:.2f}")
        update_seats(flight.flight_id, -1)
        updated = Flight.from_row(get_flight_by_id(flight.flight_id))
        after = calculate_price(updated, as_of)
        print(f"UPDATE: seats 21 → {updated.seats_remaining}; "
              f"seat factor {before.seats_factor:.2f} → {after.seats_factor:.2f}; "
              f"fare {before.price:.2f} → {after.price:.2f}")
        assert updated.seats_remaining == 20
        assert after.price > before.price
        try:
            update_seats(flight.flight_id, -21)
        except ValueError as error:
            print(f"Expected invalid update rejected: {error}")
        else:
            raise AssertionError("Invalid seat update was accepted")
        assert get_flight_by_id(flight.flight_id)[7] == 20
    finally:
        # Only remove the flight created by this demo, even if a later step fails.
        delete_flight(flight.flight_id)
    assert get_flight_by_id(flight.flight_id) is None
    print("DELETE: temporary flight removed; existing flights unchanged.")


def parse_date(value):
    """Accept only canonical calendar dates and provide a readable CLI error."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use a valid date in YYYY-MM-DD format") from error
    if parsed.strftime("%Y-%m-%d") != value:
        raise argparse.ArgumentTypeError("Use a valid date in YYYY-MM-DD format")
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search, price, and inspect flights")
    parser.add_argument("--origin", required=True, help="Origin city in the CSV")
    parser.add_argument("--destination", required=True, help="Destination city in the CSV")
    parser.add_argument("--date", required=True, type=parse_date, help="Flight date, YYYY-MM-DD")
    parser.add_argument("--as-of", type=parse_date, help="Pricing date, YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--demo-pricing", action="store_true",
        help="Compare five booking dates and demonstrate minimum/maximum fare limits",
    )
    parser.add_argument(
        "--demo-crud", "--demo-update", dest="demo_crud", action="store_true",
        help="Demonstrate CRUD, a seat-price change, and an invalid update on a temporary flight",
    )
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ValueError, FileNotFoundError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def run(args):
    as_of = args.as_of or datetime.now()
    results = search_flights(args.origin, args.destination, args.date.date().isoformat(), as_of)
    if not results:
        print("No available future flights match this search.")
        if args.demo_pricing:
            show_fare_limits_demo()
        if args.demo_crud:
            show_database_demo(as_of)
        return 0

    prices = np.asarray([price for _, price in results])
    print(f"{len(results)} flights from {args.origin} to {args.destination} on {args.date.date()}:")
    for flight, price in results:
        print(
            f"  {flight.flight_id}  {flight.departure_time}  "
            f"seats {flight.seats_remaining}/{flight.seat_capacity}  fare {price:.2f}"
        )
    print(f"Fare range: {prices.min():.2f}–{prices.max():.2f}; average: {prices.mean():.2f}")

    if args.demo_pricing:
        show_pricing_demo(results[0][0])
        show_fare_limits_demo()

    if args.demo_crud:
        show_database_demo(as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
