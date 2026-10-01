"""Administrator operations that can be called by a future frontend."""

import sqlite3
from dataclasses import asdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping

from database.db import (
    append_flight_to_csv, csv_has_flight, delete_flight, insert_flight, set_capacity,
)
from .flight import Flight


def update_capacity(flight_id: str, seat_capacity: int) -> int:
    """Save a positive total capacity, at least equal to remaining seats.

    Returns the saved capacity. Remaining seats are unchanged, including for
    sold-out flights. Raises ValueError for invalid input or a missing flight.
    """
    return set_capacity(flight_id, seat_capacity)


def add_flight(data: Mapping[str, object]) -> Flight:
    """Validate and save a complete new flight in SQLite.

    Requires all Flight fields except minimum_fare, which is calculated as
    80% of base_fare. If minimum_fare is supplied, it must match that rule.
    The flight is also appended to the project CSV (see below). If the CSV
    cannot be updated, the new SQLite row is removed again and ValueError is raised.
    """
    flight_data = dict(data)
    try:
        base_fare = Decimal(str(flight_data["base_fare"]))
        if not base_fare.is_finite():
            raise ValueError("base_fare must be finite")
        minimum_fare = (base_fare * Decimal("0.80")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if "minimum_fare" in flight_data and Decimal(str(flight_data["minimum_fare"])) != minimum_fare:
            raise ValueError("minimum_fare must equal 0.80 × base_fare")
    except (KeyError, InvalidOperation) as error:
        raise ValueError("A valid base_fare is required") from error
    flight_data["minimum_fare"] = float(minimum_fare)
    flight = Flight(**flight_data)
    if csv_has_flight(flight.flight_id):
        raise ValueError(f"Flight {flight.flight_id} already exists in the CSV")
    try:
        insert_flight(asdict(flight))
    except sqlite3.IntegrityError as error:
        raise ValueError(f"Flight could not be added: {error}") from error
    # SQLite insert is committed. Add the CSV row; if that fails, undo the insert
    # so SQLite and the CSV stay consistent.
    try:
        append_flight_to_csv(asdict(flight))
    except Exception as error:
        try:
            delete_flight(flight.flight_id)
        except Exception as rollback_error:
            raise ValueError(
                f"Flight {flight.flight_id} is in SQLite but not the CSV ({error}); "
                f"it could not be removed: {rollback_error}"
            ) from error
        raise ValueError(f"Flight was not created: {error}") from error
    return flight
