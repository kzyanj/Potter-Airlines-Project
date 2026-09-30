"""Basic flight operations for the SQLite database."""

import csv
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "potter_airlines.db"
DEFAULT_DATABASE_PATH = DATABASE_PATH
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "potter_airline_routes_dataset_regenerated.csv"


@contextmanager
def get_connection():
    """Open a database transaction and always close the connection."""
    if not DATABASE_PATH.exists():
        raise FileNotFoundError("Run python database/init_db.py first")
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _sync_seats_to_csv(flight_id, seats_remaining):
    """Copy a committed seats_remaining value into the matching CSV row.

    SQLite stays the source of truth; this only keeps the CSV in step. Only the
    seats_remaining cell of the row with this flight_id changes. The CSV is
    rewritten to a temporary file first and then swapped in, so a failed write
    cannot leave a half-written CSV. Only the real database syncs, so tests
    using a temporary database never touch the project CSV.
    """
    if DATABASE_PATH != DEFAULT_DATABASE_PATH or not CSV_PATH.exists():
        return
    temp_name = None
    try:
        with CSV_PATH.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.reader(source)
            rows = list(reader)
        header = rows[0]
        id_column = header.index("flight_id")
        seats_column = header.index("seats_remaining")
        for row in rows[1:]:
            if row and row[id_column] == flight_id:
                row[seats_column] = str(seats_remaining)
                break
        else:
            return  # flight only exists in SQLite (e.g. added by an admin)
        with tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", dir=CSV_PATH.parent, suffix=".tmp", delete=False
        ) as target:
            temp_name = target.name
            csv.writer(target, lineterminator="\n").writerows(rows)
        os.replace(temp_name, CSV_PATH)
        temp_name = None
    except Exception as error:
        raise RuntimeError(
            f"Seats for {flight_id} were saved in SQLite, but the CSV could not be updated: {error}"
        ) from error
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def get_flight_by_id(flight_id):
    """Return one flight row in the same column order as the source CSV."""
    with get_connection() as connection:
        return connection.execute(
            "SELECT flight_id, origin, destination, flight_date, departure_time, "
            "route_popularity, seat_capacity, seats_remaining, base_fare, minimum_fare, maximum_fare "
            "FROM flights WHERE flight_id = ?", (flight_id,)
        ).fetchone()


def get_flights_by_destination(destination):
    """Return flights arriving at the named city."""
    with get_connection() as connection:
        return connection.execute(
            "SELECT flight_id, origin, destination, flight_date, departure_time, seats_remaining "
            "FROM flights WHERE destination = ?", (destination,)
        ).fetchall()


def insert_flight(flight):
    """Insert a flight mapping with the same fields as the source CSV."""
    fields = (
        "flight_id", "origin", "destination", "flight_date", "departure_time",
        "route_popularity", "seat_capacity", "seats_remaining", "base_fare", "minimum_fare", "maximum_fare",
    )
    with get_connection() as connection:
        connection.execute(
            f"INSERT INTO flights ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            tuple(flight[field] for field in fields),
        )
    return flight["flight_id"]


def update_seats(flight_id, seat_change):
    """Adjust remaining seats, keeping the result between zero and capacity."""
    if isinstance(seat_change, bool) or not isinstance(seat_change, int):
        raise ValueError("seat_change must be an integer")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT seats_remaining, seat_capacity FROM flights WHERE flight_id = ?", (flight_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No flight found with flight_id {flight_id}")
        new_seats = row[0] + seat_change
        if not 0 <= new_seats <= row[1]:
            raise ValueError(f"Seats must stay between 0 and {row[1]}")
        connection.execute(
            "UPDATE flights SET seats_remaining = ? WHERE flight_id = ?", (new_seats, flight_id)
        )
    # The with-block above has committed the update; only now sync the CSV.
    _sync_seats_to_csv(flight_id, new_seats)
    return new_seats


def set_seats(flight_id, seats_remaining):
    """Set an exact seat count for an administrator, within aircraft capacity."""
    if isinstance(seats_remaining, bool) or not isinstance(seats_remaining, int):
        raise ValueError("seats_remaining must be an integer")
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE flights SET seats_remaining = ? "
            "WHERE flight_id = ? AND ? BETWEEN 0 AND seat_capacity",
            (seats_remaining, flight_id, seats_remaining),
        )
        if cursor.rowcount == 0:
            row = connection.execute(
                "SELECT seat_capacity FROM flights WHERE flight_id = ?", (flight_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"No flight found with flight_id {flight_id}")
            raise ValueError(f"Seats must stay between 0 and {row[0]}")
    # Committed at the end of the with-block; only now sync the CSV.
    _sync_seats_to_csv(flight_id, seats_remaining)
    return seats_remaining


def set_capacity(flight_id, seat_capacity):
    """Set total capacity without changing remaining seats or the source CSV."""
    if isinstance(seat_capacity, bool) or not isinstance(seat_capacity, int):
        raise ValueError("seat_capacity must be an integer")
    if not 0 < seat_capacity <= 9223372036854775807:
        raise ValueError("seat_capacity must be a positive SQLite integer")
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE flights SET seat_capacity = ? "
            "WHERE flight_id = ? AND seats_remaining <= ?",
            (seat_capacity, flight_id, seat_capacity),
        )
        if cursor.rowcount == 0:
            row = connection.execute(
                "SELECT seats_remaining FROM flights WHERE flight_id = ?", (flight_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"No flight found with flight_id {flight_id}")
            raise ValueError(f"Capacity must be at least the remaining seats ({row[0]})")
    return seat_capacity


def delete_flight(flight_id):
    """Delete a flight from SQLite, leaving the source CSV unchanged."""
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM flights WHERE flight_id = ?", (flight_id,))
        return cursor.rowcount > 0
