"""Basic flight operations for the SQLite database."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "potter_airlines.db"


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
    return seats_remaining


def delete_flight(flight_id):
    """Delete a flight from SQLite, leaving the source CSV unchanged."""
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM flights WHERE flight_id = ?", (flight_id,))
        return cursor.rowcount > 0
