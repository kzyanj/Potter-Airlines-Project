"""Administrator operations that can be called by a future frontend."""

import sqlite3
from dataclasses import asdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping

from database.db import insert_flight
from .flight import Flight


def add_flight(data: Mapping[str, object]) -> Flight:
    """Validate and save a complete new flight in SQLite.

    Requires all Flight fields except minimum_fare, which is calculated as
    75% of base_fare. If minimum_fare is supplied, it must match that rule.
    Changes to SQLite do not modify the source CSV.
    """
    flight_data = dict(data)
    try:
        base_fare = Decimal(str(flight_data["base_fare"]))
        if not base_fare.is_finite():
            raise ValueError("base_fare must be finite")
        minimum_fare = (base_fare * Decimal("0.75")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if "minimum_fare" in flight_data and Decimal(str(flight_data["minimum_fare"])) != minimum_fare:
            raise ValueError("minimum_fare must equal 0.75 × base_fare")
    except (KeyError, InvalidOperation) as error:
        raise ValueError("A valid base_fare is required") from error
    flight_data["minimum_fare"] = float(minimum_fare)
    flight = Flight(**flight_data)
    try:
        insert_flight(asdict(flight))
    except sqlite3.IntegrityError as error:
        raise ValueError(f"Flight could not be added: {error}") from error
    return flight
