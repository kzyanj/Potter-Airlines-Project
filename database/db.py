"""
Potter Airlines - basic database CRUD layer.

Small, beginner-friendly functions for reading and writing the SQLite
database created by database/init_db.py. This is only the CRUD
foundation the rubric asks for - no pricing, demand scoring, itinerary
search, or Flight-class logic lives here.

Run with:  python database/db.py
"""

import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "potter_airlines.db"


def get_connection():
    """Open a connection to the Potter Airlines database with foreign
    key enforcement turned on (SQLite does not enable this by default).
    """
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


# --------------------------------------------------------------------
# SELECT
# --------------------------------------------------------------------

def get_flight_by_id(flight_id):
    """Return one flight as a tuple, including its aircraft capacity, or
    None if no such flight exists.

    Tuple order: (flight_id, route_id, aircraft_type_id, departure_datetime,
    arrival_datetime, seats_remaining, capacity)
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT flights.flight_id, flights.route_id, flights.aircraft_type_id,
                   flights.departure_datetime, flights.arrival_datetime,
                   flights.seats_remaining, aircraft_types.capacity
            FROM flights
            JOIN aircraft_types ON flights.aircraft_type_id = aircraft_types.aircraft_type_id
            WHERE flights.flight_id = ?
            """,
            (flight_id,),
        )
        return cursor.fetchone()
    finally:
        connection.close()


def get_flights_by_destination(destination):
    """Return every flight whose route destination matches the given
    airport code, joining flights to routes.
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT flights.flight_id, routes.origin, routes.destination,
                   flights.departure_datetime, flights.seats_remaining
            FROM flights
            JOIN routes ON flights.route_id = routes.route_id
            WHERE routes.destination = ?
            """,
            (destination,),
        )
        return cursor.fetchall()
    finally:
        connection.close()


def get_bookings_for_flight(flight_id):
    """Return every booking made for a given flight."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT booking_id, flight_id, number_of_passengers, booking_datetime, price_paid
            FROM bookings
            WHERE flight_id = ?
            """,
            (flight_id,),
        )
        return cursor.fetchall()
    finally:
        connection.close()


# --------------------------------------------------------------------
# INSERT
# --------------------------------------------------------------------

def create_booking(flight_id, number_of_passengers, booking_datetime, price_paid):
    """Insert a new booking row and return its booking_id.

    price_paid is supplied by the caller rather than calculated here,
    since pricing logic will be implemented later elsewhere.
    """
    if number_of_passengers <= 0:
        raise ValueError("number_of_passengers must be greater than 0")
    if price_paid < 0:
        raise ValueError("price_paid cannot be negative")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO bookings (flight_id, number_of_passengers, booking_datetime, price_paid)
            VALUES (?, ?, ?, ?)
            """,
            (flight_id, number_of_passengers, booking_datetime, price_paid),
        )
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# --------------------------------------------------------------------
# UPDATE
# --------------------------------------------------------------------

def update_seats(flight_id, seat_change):
    """Adjust a flight's seats_remaining by seat_change (positive to add
    seats back, negative to consume them). Returns the new seat count.

    Validates 0 <= new seats_remaining <= aircraft capacity BEFORE writing
    anything, so a failed validation leaves seats_remaining untouched.
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT flights.seats_remaining, aircraft_types.capacity
            FROM flights
            JOIN aircraft_types ON flights.aircraft_type_id = aircraft_types.aircraft_type_id
            WHERE flights.flight_id = ?
            """,
            (flight_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"No flight found with flight_id {flight_id}")

        current_seats, capacity = row
        new_seats = current_seats + seat_change

        if not (0 <= new_seats <= capacity):
            raise ValueError(
                f"Invalid seat update for {flight_id}: {current_seats} + ({seat_change}) "
                f"= {new_seats}, but capacity is {capacity}"
            )

        cursor.execute(
            "UPDATE flights SET seats_remaining = ? WHERE flight_id = ?",
            (new_seats, flight_id),
        )
        connection.commit()
        return new_seats
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# --------------------------------------------------------------------
# DELETE
# --------------------------------------------------------------------

def delete_booking(booking_id):
    """Delete a booking by id. Returns True if a row was actually removed.

    Does not restore seats automatically - whether cancellation should
    affect seat inventory will be decided later.
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM bookings WHERE booking_id = ?", (booking_id,))
        deleted = cursor.rowcount > 0
        connection.commit()
        return deleted
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# --------------------------------------------------------------------
# Demonstration
# --------------------------------------------------------------------

def _demo():
    """Exercise every CRUD function against one flight, then leave the
    database as close to its original state as possible.
    """
    demo_flight_id = "PA1001"

    print("SELECT:")
    flight = get_flight_by_id(demo_flight_id)
    if flight is None:
        print(f"  Flight {demo_flight_id} not found - run database/init_db.py first.")
        return
    _, route_id, aircraft_type_id, departure, arrival, seats_remaining, capacity = flight
    print(
        f"  {demo_flight_id} | route {route_id} | aircraft {aircraft_type_id} "
        f"| departs {departure} | seats remaining {seats_remaining} of {capacity}"
    )
    original_seats = seats_remaining

    print("\nINSERT:")
    booking_id = create_booking(
        flight_id=demo_flight_id,
        number_of_passengers=1,
        booking_datetime="2026-09-15 12:00:00",
        price_paid=0.0,
    )
    print(f"  Created booking ID {booking_id}")

    print("\nUPDATE:")
    new_seats = update_seats(demo_flight_id, -1)
    print(f"  Seats changed from {original_seats} to {new_seats}")

    print("\nSELECT (after update):")
    updated_flight = get_flight_by_id(demo_flight_id)
    print(f"  {demo_flight_id} | seats remaining {updated_flight[5]} of {updated_flight[6]}")

    print("\nDELETE:")
    deleted = delete_booking(booking_id)
    print(f"  Booking removed: {deleted}")

    print("\nCleanup:")
    restored_seats = update_seats(demo_flight_id, 1)
    print(f"  Seats restored to {restored_seats}")

    print("\nEdge case - invalid seat update:")
    current_seats = get_flight_by_id(demo_flight_id)[5]
    oversized_change = -(current_seats + 20)  # guaranteed to go below zero
    try:
        update_seats(demo_flight_id, oversized_change)
        print("  ERROR: expected a ValueError but none was raised")
    except ValueError as error:
        print(f"  Correctly raised ValueError: {error}")

    unchanged_flight = get_flight_by_id(demo_flight_id)
    print(f"  Seats remaining still {unchanged_flight[5]} (unchanged)")


if __name__ == "__main__":
    _demo()
