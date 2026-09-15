"""
Potter Airlines - SQLite database initializer.

Creates database/potter_airlines.db from database/schema.sql and loads
the synthetic CSV data from data/ into it. This step only builds the
relational database foundation - no pricing, demand, search, or booking
logic is implemented here.

Run with:  python database/init_db.py
"""

import csv
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DATA_DIR = PROJECT_ROOT / "data"

DATABASE_PATH = DATABASE_DIR / "potter_airlines.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"

AIRCRAFT_CSV_PATH = DATA_DIR / "aircraft_types.csv"
ROUTES_CSV_PATH = DATA_DIR / "routes.csv"
FLIGHTS_CSV_PATH = DATA_DIR / "flights.csv"


def create_database():
    """Start from a clean database file with foreign keys enforced.

    SQLite does not enforce foreign keys by default, so every connection
    must turn this on explicitly.
    """
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def load_schema(connection):
    """Run schema.sql to create all tables."""
    schema_sql = SCHEMA_PATH.read_text()
    connection.executescript(schema_sql)


def _read_csv_rows(csv_path):
    with open(csv_path, newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def load_aircraft_types(connection):
    """Insert every row from aircraft_types.csv. Returns the row count."""
    rows = _read_csv_rows(AIRCRAFT_CSV_PATH)
    cursor = connection.cursor()
    for row in rows:
        cursor.execute(
            """
            INSERT INTO aircraft_types (aircraft_type_id, aircraft_name, capacity)
            VALUES (?, ?, ?)
            """,
            (row["aircraft_type_id"], row["aircraft_name"], int(row["capacity"])),
        )
    return len(rows)


def load_routes(connection):
    """Insert every row from routes.csv. Returns the row count."""
    rows = _read_csv_rows(ROUTES_CSV_PATH)
    cursor = connection.cursor()
    for row in rows:
        cursor.execute(
            """
            INSERT INTO routes (
                route_id, origin, destination, origin_city,
                destination_city, route_popularity, scheduled_duration_minutes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["route_id"],
                row["origin"],
                row["destination"],
                row["origin_city"],
                row["destination_city"],
                row["route_popularity"],
                int(row["scheduled_duration_minutes"]),
            ),
        )
    return len(rows)


def load_flights(connection):
    """Insert every row from flights.csv. Returns the row count.

    Must run after load_aircraft_types() and load_routes() because
    flights references both of those tables by foreign key.
    """
    rows = _read_csv_rows(FLIGHTS_CSV_PATH)
    cursor = connection.cursor()
    for row in rows:
        cursor.execute(
            """
            INSERT INTO flights (
                flight_id, route_id, aircraft_type_id,
                departure_datetime, arrival_datetime, seats_remaining
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["flight_id"],
                row["route_id"],
                row["aircraft_type_id"],
                row["departure_datetime"],
                row["arrival_datetime"],
                int(row["seats_remaining"]),
            ),
        )
    return len(rows)


def validate_database(connection, expected_counts):
    """Check the loaded database against the source CSVs and its own
    relational rules. Raises AssertionError on any failure.
    """
    cursor = connection.cursor()

    # 1-3. Table row counts match the number of rows loaded from each CSV.
    for table, expected_count in expected_counts.items():
        actual_count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert actual_count == expected_count, (
            f"{table} has {actual_count} rows, expected {expected_count}"
        )

    # 4. Every flight references a valid route.
    orphan_routes = cursor.execute(
        """
        SELECT COUNT(*) FROM flights
        LEFT JOIN routes ON flights.route_id = routes.route_id
        WHERE routes.route_id IS NULL
        """
    ).fetchone()[0]
    assert orphan_routes == 0, f"{orphan_routes} flights reference a missing route"

    # 5. Every flight references a valid aircraft type.
    orphan_aircraft = cursor.execute(
        """
        SELECT COUNT(*) FROM flights
        LEFT JOIN aircraft_types ON flights.aircraft_type_id = aircraft_types.aircraft_type_id
        WHERE aircraft_types.aircraft_type_id IS NULL
        """
    ).fetchone()[0]
    assert orphan_aircraft == 0, f"{orphan_aircraft} flights reference a missing aircraft type"

    # 6. No flight has negative seats remaining.
    negative_seats = cursor.execute(
        "SELECT COUNT(*) FROM flights WHERE seats_remaining < 0"
    ).fetchone()[0]
    assert negative_seats == 0, f"{negative_seats} flights have negative seats_remaining"

    # 7. No flight has more seats remaining than its aircraft's capacity.
    over_capacity = cursor.execute(
        """
        SELECT COUNT(*) FROM flights
        JOIN aircraft_types ON flights.aircraft_type_id = aircraft_types.aircraft_type_id
        WHERE flights.seats_remaining > aircraft_types.capacity
        """
    ).fetchone()[0]
    assert over_capacity == 0, f"{over_capacity} flights have seats_remaining above capacity"

    # 8. No orphan foreign-key records anywhere in the database.
    violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    assert not violations, f"Foreign key violations found: {violations}"


def show_example_joins(connection):
    """Print a few example relational queries to demonstrate the schema."""
    cursor = connection.cursor()

    print("\nExample 1: Flights joined to Routes")
    rows = cursor.execute(
        """
        SELECT flights.flight_id, routes.origin, routes.destination, flights.departure_datetime
        FROM flights
        JOIN routes ON flights.route_id = routes.route_id
        LIMIT 5
        """
    ).fetchall()
    for flight_id, origin, destination, departure in rows:
        print(f"  {flight_id} | {origin} -> {destination} | departs {departure}")

    print("\nExample 2: Flights joined to Aircraft Types")
    rows = cursor.execute(
        """
        SELECT flights.flight_id, aircraft_types.aircraft_name,
               aircraft_types.capacity, flights.seats_remaining
        FROM flights
        JOIN aircraft_types ON flights.aircraft_type_id = aircraft_types.aircraft_type_id
        LIMIT 5
        """
    ).fetchall()
    for flight_id, aircraft_name, capacity, seats_remaining in rows:
        print(f"  {flight_id} | {aircraft_name} | capacity {capacity} | seats remaining {seats_remaining}")

    print("\nExample 3: Flights joined to Routes and Aircraft Types")
    rows = cursor.execute(
        """
        SELECT flights.flight_id, routes.origin, routes.destination,
               flights.departure_datetime, flights.arrival_datetime,
               aircraft_types.aircraft_name, aircraft_types.capacity,
               flights.seats_remaining
        FROM flights
        JOIN routes ON flights.route_id = routes.route_id
        JOIN aircraft_types ON flights.aircraft_type_id = aircraft_types.aircraft_type_id
        LIMIT 5
        """
    ).fetchall()
    for flight_id, origin, destination, departure, arrival, aircraft_name, capacity, seats_remaining in rows:
        print(
            f"  {flight_id} | {origin} -> {destination} | {departure} to {arrival} "
            f"| {aircraft_name} (cap {capacity}) | seats remaining {seats_remaining}"
        )


def main():
    connection = create_database()
    try:
        load_schema(connection)

        # Insert order matters: aircraft_types and routes must exist
        # before flights, since flights has foreign keys to both.
        aircraft_count = load_aircraft_types(connection)
        route_count = load_routes(connection)
        flight_count = load_flights(connection)
        connection.commit()

        validate_database(
            connection,
            expected_counts={
                "aircraft_types": aircraft_count,
                "routes": route_count,
                "flights": flight_count,
            },
        )

        booking_count = connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]

        print(f"Database created at: {DATABASE_PATH}")
        print(f"Aircraft types inserted: {aircraft_count}")
        print(f"Routes inserted: {route_count}")
        print(f"Flights inserted: {flight_count}")
        print(f"Bookings: {booking_count}")

        show_example_joins(connection)

        print("\nAll validation checks passed.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
