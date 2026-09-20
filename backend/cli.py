"""Run a small end-to-end Potter Airlines backend demonstration.

Example:
    python -m backend.cli --origin Toronto --destination Montreal \
        --date 2026-10-02 --as-of 2026-09-20 --demo-pricing
"""

import argparse
from datetime import datetime, timedelta

import numpy as np

from database.db import get_flight_by_id, update_seats
from .pricing import calculate_price
from .search import search_flights


def show_pricing_demo(flight):
    """Compare the same flight at four simulated search dates."""
    print(f"\nSimulated fare calculation for {flight.flight_id} (base {flight.base_fare:.2f}, "
          f"minimum {flight.minimum_fare:.2f}, maximum {flight.maximum_fare:.2f}):")
    for days_before in (45, 20, 7, 1):
        simulated_time = flight.departure - timedelta(days=days_before)
        result = calculate_price(flight, simulated_time)
        print(
            f"  {simulated_time.date()} ({days_before} {'day' if days_before == 1 else 'days'} before): "
            f"{flight.base_fare:.2f} × route {result.route_factor:.2f} "
            f"× weekday {result.day_factor:.2f} "
            f"× time {result.time_of_day_factor:.2f} "
            f"× seats {result.seats_factor:.2f} "
            f"× season {result.season_factor:.2f} "
            f"× days {result.days_until_flight_factor:.2f} "
            f"→ fare {result.price:.2f}"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search, price, and inspect flights")
    parser.add_argument("--origin", required=True, help="Origin city in the CSV")
    parser.add_argument("--destination", required=True, help="Destination city in the CSV")
    parser.add_argument("--date", required=True, help="Flight date, YYYY-MM-DD")
    parser.add_argument("--as-of", help="Pricing date, YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--demo-pricing", action="store_true",
        help="Compare one flight's fare at four simulated search dates",
    )
    parser.add_argument(
        "--demo-update", action="store_true",
        help="Temporarily reduce one seat, show an invalid update, then restore it",
    )
    args = parser.parse_args(argv)
    as_of = datetime.strptime(args.as_of, "%Y-%m-%d") if args.as_of else datetime.now()

    results = search_flights(args.origin, args.destination, args.date, as_of)
    if not results:
        print("No available future flights match this search.")
        return 0

    prices = np.asarray([price for _, price in results])
    print(f"{len(results)} flights from {args.origin} to {args.destination} on {args.date}:")
    for flight, price in results:
        print(
            f"  {flight.flight_id}  {flight.departure_time}  "
            f"seats {flight.seats_remaining}/{flight.seat_capacity}  fare {price:.2f}"
        )
    print(f"Fare range: {prices.min():.2f}–{prices.max():.2f}; average: {prices.mean():.2f}")

    if args.demo_pricing:
        show_pricing_demo(results[0][0])

    if args.demo_update:
        flight = results[0][0]
        original = flight.seats_remaining
        try:
            changed = update_seats(flight.flight_id, -1)
            print(f"Seat update for {flight.flight_id}: {original} → {changed}")
            try:
                update_seats(flight.flight_id, -(changed + 1))
            except ValueError as error:
                print(f"Expected invalid update rejected: {error}")
            else:
                raise AssertionError("Invalid seat update was accepted")
            assert get_flight_by_id(flight.flight_id)[7] == changed
        finally:
            update_seats(flight.flight_id, original - get_flight_by_id(flight.flight_id)[7])
        print(f"Seats restored to {get_flight_by_id(flight.flight_id)[7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
