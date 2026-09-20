"""Dynamic fares using the team's six-factor pricing table."""

from dataclasses import dataclass
from datetime import datetime
from math import floor, isfinite

from .flight import Flight

ROUTE_FACTORS = {"Low": 0.95, "Medium": 1.00, "High": 1.10}


@dataclass(frozen=True)
class PriceResult:
    flight_id: str
    price: float
    route_factor: float
    day_factor: float
    time_of_day_factor: float
    seats_factor: float
    season_factor: float
    days_until_flight_factor: float


def calculate_price(flight: Flight, as_of: datetime | None = None) -> PriceResult:
    """Apply all six factors and bound the result by minimum and maximum fare.

    Days until flight uses calendar dates: today is day 0, tomorrow is day 1.
    """
    as_of = as_of or datetime.now()
    if not all(isfinite(fare) for fare in (flight.minimum_fare, flight.base_fare, flight.maximum_fare)):
        raise ValueError("Fares must be finite")
    departure = flight.departure
    if departure <= as_of:
        raise ValueError("Cannot price a departed flight")

    # Route Popularity factor: Low 0.95, Medium 1.00, High 1.10.
    route_factor = ROUTE_FACTORS[flight.route_popularity]

    # Day of Week factor: weekdays 1.00; Saturday and Sunday 1.05.
    day_factor = 1.05 if departure.weekday() >= 5 else 1.00

    # Time of Day: 9:00 PM–5:59 AM (overnight) = 0.90.
    # Time of Day: 6:00 AM–4:59 PM (daytime) = 1.00.
    # Time of Day: 5:00 PM–8:59 PM (evening) = 1.05.
    hour = departure.hour
    time_of_day_factor = 0.90 if hour >= 21 or hour < 6 else 1.00 if hour < 17 else 1.05

    # Seats Remaining: 51–100% (high availability) = 0.95.
    # Seats Remaining: 21–50% (moderate availability) = 1.00.
    # Seats Remaining: 11–20% (low availability) = 1.10.
    # Seats Remaining: 0–10% (very low availability) = 1.25.
    remaining_fraction = flight.seat_fraction
    seats_factor = (
        1.25 if remaining_fraction <= 0.10 else
        1.10 if remaining_fraction <= 0.20 else
        1.00 if remaining_fraction <= 0.50 else 0.95
    )
    # Seasonality factor
    # Seasonality: Jan 6–Mar 31 (low season) = 0.90.
    # Seasonality: Apr 1–Jun 14 (regular) = 1.00.
    # Seasonality: Jun 15–Aug 31 (peak) = 1.10.
    # Seasonality: Sep 1–Dec 19 (regular) = 1.00.
    # Seasonality: Dec 20–Jan 5 (peak holiday) = 1.20.
    month_day = (departure.month, departure.day)
    if month_day >= (12, 20) or month_day <= (1, 5):
        season_factor = 1.20
    elif (1, 6) <= month_day <= (3, 31):
        season_factor = 0.90
    elif (6, 15) <= month_day <= (8, 31):
        season_factor = 1.10
    else:
        season_factor = 1.00

    # Days Until Flight factor: 0–3, 4–14, 15–30, or 31+ calendar days.
    days = (departure.date() - as_of.date()).days
    days_until_flight_factor = 1.30 if days <= 3 else 1.15 if days <= 14 else 1.00 if days <= 30 else 0.95

    # Start with base_fare and multiply six factors:
    # route popularity, weekday/weekend, departure time, seat availability,
    # season, and days until departure.
    # Values below 1 discount the fare; values above 1 increase it.
    # After multiplication, apply the fare limits and round to two decimals.
    raw = flight.base_fare * route_factor * day_factor * time_of_day_factor
    raw *= seats_factor * season_factor * days_until_flight_factor
    bounded = min(flight.maximum_fare, max(flight.minimum_fare, raw))
    price = floor(bounded * 100 + 0.5 + 1e-9) / 100
    return PriceResult(
        flight.flight_id, price, route_factor, day_factor, time_of_day_factor,
        seats_factor, season_factor, days_until_flight_factor,
    )
