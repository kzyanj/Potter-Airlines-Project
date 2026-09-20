"""Search flights and calculate fares across a result set."""

from datetime import datetime

from database.db import get_connection
from .flight import Flight

FLIGHT_COLUMNS = (
    "flight_id, origin, destination, flight_date, departure_time, route_popularity, "
    "seat_capacity, seats_remaining, base_fare, minimum_fare, maximum_fare"
)
FUTURE_AVAILABLE = (
    "seats_remaining > 0 AND "
    "(flight_date > ? OR (flight_date = ? AND departure_time > ?))"
)


def _future_params(as_of: datetime):
    return (as_of.date().isoformat(), as_of.date().isoformat(), as_of.strftime("%H:%M"))


def get_origins(as_of: datetime | None = None) -> list[str]:
    """Cities with at least one future flight that has seats available."""
    as_of = as_of or datetime.now()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT DISTINCT origin FROM flights WHERE {FUTURE_AVAILABLE} ORDER BY origin",
            _future_params(as_of),
        ).fetchall()
    return [row[0] for row in rows]


def get_destinations(origin: str, as_of: datetime | None = None) -> list[str]:
    """Destinations available from the selected origin."""
    as_of = as_of or datetime.now()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT DISTINCT destination FROM flights WHERE origin = ? AND {FUTURE_AVAILABLE} "
            "ORDER BY destination",
            (origin, *_future_params(as_of)),
        ).fetchall()
    return [row[0] for row in rows]


def get_flight_dates(origin: str, destination: str, as_of: datetime | None = None) -> list[str]:
    """Dates with available flights on the selected route."""
    as_of = as_of or datetime.now()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT DISTINCT flight_date FROM flights "
            f"WHERE origin = ? AND destination = ? AND {FUTURE_AVAILABLE} "
            "ORDER BY flight_date",
            (origin, destination, *_future_params(as_of)),
        ).fetchall()
    return [row[0] for row in rows]


def search_flights(origin: str, destination: str, flight_date: str, as_of: datetime | None = None):
    """Return (Flight, price) pairs sorted by NumPy-calculated fare and time."""
    # --- Step 1: Check the requested date and set the time of the search. ---
    datetime.strptime(flight_date, "%Y-%m-%d")
    as_of = as_of or datetime.now()

    # --- Step 2: Load flights on that route and date that still have seats. ---
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {FLIGHT_COLUMNS} FROM flights "
            "WHERE origin = ? AND destination = ? AND flight_date = ? AND seats_remaining > 0",
            (origin, destination, flight_date),
        ).fetchall()

    # --- Step 3: Convert database rows to Flight objects and remove departed flights. ---
    flights = [Flight.from_row(row) for row in rows]
    flights = [flight for flight in flights if flight.departure > as_of]

    # --- Step 4: Calculate all remaining fares together with NumPy. ---
    prices = analyze_fares(flights, as_of)

    # --- Step 5: Return flights sorted by fare, then departure time. ---
    return sorted(
        ((flight, float(price)) for flight, price in zip(flights, prices)),
        key=lambda result: (result[1], result[0].departure),
    )


def analyze_fares(flights: list[Flight], as_of: datetime | None = None):
    """Vectorized NumPy calculation for a collection of flights.

    Returns one fare per input flight, in input order. Install requirements.txt
    before calling this function.
    """
    import numpy as np

    as_of = as_of or datetime.now()
    if any(flight.departure <= as_of for flight in flights):
        raise ValueError("Cannot price a departed flight")
    if not flights:
        return np.array([], dtype=float)
    departures = [flight.departure for flight in flights]
    days = np.array([(departure.date() - as_of.date()).days for departure in departures])
    remaining = np.array([flight.seats_remaining for flight in flights], dtype=float)
    capacity = np.array([flight.seat_capacity for flight in flights], dtype=float)
    base = np.array([flight.base_fare for flight in flights], dtype=float)
    minimum = np.array([flight.minimum_fare for flight in flights], dtype=float)
    maximum = np.array([flight.maximum_fare for flight in flights], dtype=float)
    if not np.all(np.isfinite(minimum)) or not np.all(np.isfinite(base)) or not np.all(np.isfinite(maximum)):
        raise ValueError("Fares must be finite")

    route_factor = np.array([{"Low": 0.95, "Medium": 1.00, "High": 1.10}[flight.route_popularity] for flight in flights])
    weekdays = np.array([departure.weekday() for departure in departures])
    day_factor = np.where(weekdays >= 5, 1.05, 1.00)
    hours = np.array([departure.hour for departure in departures])
    time_of_day_factor = np.where((hours >= 21) | (hours < 6), 0.90, np.where(hours < 17, 1.00, 1.05))

    seat_fraction = remaining / capacity
    seats_factor = np.select(
        [seat_fraction <= 0.10, seat_fraction <= 0.20, seat_fraction <= 0.50],
        [1.25, 1.10, 1.00], default=0.95,
    )
    month_days = np.array([departure.month * 100 + departure.day for departure in departures])
    season_factor = np.select(
        [(month_days >= 1220) | (month_days <= 105),
         (month_days >= 106) & (month_days <= 331),
         (month_days >= 615) & (month_days <= 831)],
        [1.20, 0.90, 1.10], default=1.00,
    )
    days_until_flight_factor = np.select(
        [days <= 3, days <= 14, days <= 30],
        [1.30, 1.15, 1.00], default=0.95,
    )
    raw = base * route_factor * day_factor * time_of_day_factor
    raw *= seats_factor * season_factor * days_until_flight_factor
    return np.floor(np.clip(raw, minimum, maximum) * 100 + 0.5 + 1e-9) / 100
