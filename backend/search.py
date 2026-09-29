"""Search flights and calculate fares across a result set."""

from datetime import datetime

from database.db import get_connection
from .flight import Flight
from .pricing import (
    ROUTE_FACTORS, SEAT_FACTOR_BANDS, DAYS_FACTOR_BANDS,
    VERY_EARLY_FACTOR, season_factor_for,
)

FLIGHT_COLUMNS = (
    "flight_id, origin, destination, flight_date, departure_time, route_popularity, "
    "seat_capacity, seats_remaining, base_fare, minimum_fare, maximum_fare"
)
FUTURE_FLIGHTS = (
    "(flight_date > ? OR (flight_date = ? AND departure_time > ?))"
)


def _future_params(as_of: datetime):
    return (as_of.date().isoformat(), as_of.date().isoformat(), as_of.strftime("%H:%M"))


def get_origins(as_of: datetime | None = None) -> list[str]:
    """Cities with at least one future flight, including sold-out flights."""
    as_of = as_of or datetime.now()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT DISTINCT origin FROM flights WHERE {FUTURE_FLIGHTS} ORDER BY origin",
            _future_params(as_of),
        ).fetchall()
    return [row[0] for row in rows]


def get_destinations(origin: str, as_of: datetime | None = None) -> list[str]:
    """Destinations available from the selected origin."""
    as_of = as_of or datetime.now()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT DISTINCT destination FROM flights WHERE origin = ? AND {FUTURE_FLIGHTS} "
            "ORDER BY destination",
            (origin, *_future_params(as_of)),
        ).fetchall()
    return [row[0] for row in rows]


def get_flight_dates(origin: str, destination: str, as_of: datetime | None = None) -> list[str]:
    """Dates with future flights on the selected route, including sold-out flights."""
    as_of = as_of or datetime.now()
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT DISTINCT flight_date FROM flights "
            f"WHERE origin = ? AND destination = ? AND {FUTURE_FLIGHTS} "
            "ORDER BY flight_date",
            (origin, destination, *_future_params(as_of)),
        ).fetchall()
    return [row[0] for row in rows]


def search_flights(origin: str, destination: str, flight_date: str, as_of: datetime | None = None):
    """Return (Flight, price) pairs; sold-out flights have price None and sort last."""
    # --- Step 1: Check the requested date and set the time of the search. ---
    if not isinstance(origin, str) or not isinstance(destination, str):
        raise ValueError("Origin and destination must be city names")
    origin, destination = origin.strip(), destination.strip()
    if not origin or not destination or origin == destination:
        raise ValueError("Choose different, non-empty origin and destination cities")
    if not isinstance(flight_date, str):
        raise ValueError("flight_date must use YYYY-MM-DD")
    try:
        parsed_date = datetime.strptime(flight_date, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("flight_date must use a valid YYYY-MM-DD date") from error
    if parsed_date.strftime("%Y-%m-%d") != flight_date:
        raise ValueError("flight_date must use YYYY-MM-DD")
    if as_of is not None and not isinstance(as_of, datetime):
        raise ValueError("as_of must be a datetime")
    as_of = as_of or datetime.now()

    # --- Step 2: Load all flights on that route and date. ---
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {FLIGHT_COLUMNS} FROM flights "
            "WHERE origin = ? AND destination = ? AND flight_date = ?",
            (origin, destination, flight_date),
        ).fetchall()

    # --- Step 3: Convert database rows to Flight objects and remove departed flights. ---
    flights = [Flight.from_row(row) for row in rows]
    flights = [flight for flight in flights if flight.departure > as_of]

    # --- Step 4: Calculate all remaining fares together with NumPy. ---
    available = [flight for flight in flights if flight.seats_remaining > 0]
    prices = analyze_fares(available, as_of)
    results = [(flight, float(price)) for flight, price in zip(available, prices)]
    results.extend((flight, None) for flight in flights if flight.seats_remaining == 0)

    # --- Step 5: Return flights sorted by fare, then departure time. ---
    return sorted(
        results,
        key=lambda result: (result[1] is None, result[1] if result[1] is not None else 0,
                            result[0].departure),
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
    if any(flight.seats_remaining == 0 for flight in flights):
        raise ValueError("No ticket available: flight is sold out")
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

    route_factor = np.array([ROUTE_FACTORS[flight.route_popularity] for flight in flights])
    seat_fraction = remaining / capacity
    seats_factor = np.select(
        [seat_fraction <= upper for upper, _ in SEAT_FACTOR_BANDS],
        [factor for _, factor in SEAT_FACTOR_BANDS],
    )
    season_factor = np.array([season_factor_for(departure) for departure in departures])
    days_until_flight_factor = np.select(
        [days <= upper for upper, _ in DAYS_FACTOR_BANDS],
        [factor for _, factor in DAYS_FACTOR_BANDS], default=VERY_EARLY_FACTOR,
    )
    raw = base * route_factor
    raw *= seats_factor * season_factor * days_until_flight_factor
    return np.floor(np.clip(raw, minimum, maximum) * 100 + 0.5 + 1e-9) / 100
