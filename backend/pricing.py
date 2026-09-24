"""Dynamic fares using the team's four-factor pricing table."""

from dataclasses import dataclass
from datetime import datetime
from math import floor, isfinite

from .flight import Flight

# Fare = base fare × route × seats × season × days until flight,
# then apply minimum/maximum fare limits and round to two decimal places.
# A factor below 1 discounts the fare; above 1 increases it; 1 leaves it unchanged.

# Route popularity: Low = 0.97, Medium = 1.00, High = 1.06.
ROUTE_FACTORS = {"Low": 0.97, "Medium": 1.00, "High": 1.06}

# Seats remaining / capacity: Critical (0–5%] = 1.30,
# Very Low (5–10%] = 1.22, Low (10–20%] = 1.15,
# Moderate (20–40%] = 1.05, High (40–65%] = 0.97,
# Very High (65–100%] = 0.92. Zero seats means no ticket is available.
# Each tuple is (inclusive upper bound, multiplier); the first match wins.
# Use actual fractions without rounding; (a–b] means greater than a, up to b.
SEAT_FACTOR_BANDS = ((0.05, 1.30), (0.10, 1.22), (0.20, 1.15),
                     (0.40, 1.05), (0.65, 0.97), (1.00, 0.92))

# Calendar days until departure: Last Minute (0–3) = 1.30,
# Soon (4–14) = 1.15, Near Term (15–30) = 1.05,
# Standard (31–60) = 1.00, Very Early (61+) = 0.95.
# Each tuple is (inclusive upper bound in days, multiplier).
DAYS_FACTOR_BANDS = ((3, 1.30), (14, 1.15), (30, 1.05), (60, 1.00))
VERY_EARLY_FACTOR = 0.95

# Seasonality uses the departure date, with inclusive date ranges:
# Low: Jan 6–Mar 31 and Nov 1–Dec 19 = 0.90.
# Regular: Apr 1–Jun 24 and Sep 1–Oct 31 = 1.00.
# Peak: Jun 25–Aug 31 = 1.12; Peak Holiday: Dec 20–Jan 5 = 1.25.


def season_factor_for(departure: datetime) -> float:
    """Return the seasonal multiplier for the flight's departure date.

    This factor multiplies the base fare alongside the other three factors.
    Date ranges include both endpoints and repeat every year.
    """
    # Compare (month, day) pairs so the rule does not depend on the year.
    month_day = (departure.month, departure.day)
    # Peak Holiday: Dec 20–Jan 5, a 25% increase (1.25×).
    # The range crosses New Year, so either side of the year qualifies.
    if month_day >= (12, 20) or month_day <= (1, 5):
        return 1.25
    # Low Season: Jan 6–Mar 31 or Nov 1–Dec 19, a 10% discount (0.90×).
    if (1, 6) <= month_day <= (3, 31) or (11, 1) <= month_day <= (12, 19):
        return 0.90
    # Peak Season: Jun 25–Aug 31, a 12% increase (1.12×).
    if (6, 25) <= month_day <= (8, 31):
        return 1.12
    # Regular Season: Apr 1–Jun 24 or Sep 1–Oct 31, no adjustment (1.00×).
    return 1.00


@dataclass(frozen=True)
class PriceResult:
    flight_id: str
    price: float
    route_factor: float
    seats_factor: float
    season_factor: float
    days_until_flight_factor: float


def calculate_price(flight: Flight, as_of: datetime | None = None) -> PriceResult:
    """Apply all four factors and bound the result by minimum and maximum fare.

    Days until flight uses calendar dates: today is day 0, tomorrow is day 1.
    """
    as_of = as_of or datetime.now()
    if not all(isfinite(fare) for fare in (flight.minimum_fare, flight.base_fare, flight.maximum_fare)):
        raise ValueError("Fares must be finite")
    departure = flight.departure
    if departure <= as_of:
        raise ValueError("Cannot price a departed flight")

    if flight.seats_remaining == 0:
        raise ValueError("No ticket available: flight is sold out")

    route_factor = ROUTE_FACTORS[flight.route_popularity]
    seats_factor = next(factor for upper, factor in SEAT_FACTOR_BANDS
                        if flight.seat_fraction <= upper)
    season_factor = season_factor_for(departure)
    # Calendar days: today is day 0, regardless of departure time.
    days = (departure.date() - as_of.date()).days
    days_until_flight_factor = next(
        (factor for upper, factor in DAYS_FACTOR_BANDS if days <= upper),
        VERY_EARLY_FACTOR,
    )

    raw = flight.base_fare * route_factor
    raw *= seats_factor * season_factor * days_until_flight_factor
    bounded = min(flight.maximum_fare, max(flight.minimum_fare, raw))
    price = floor(bounded * 100 + 0.5 + 1e-9) / 100
    return PriceResult(
        flight.flight_id, price, route_factor,
        seats_factor, season_factor, days_until_flight_factor,
    )
