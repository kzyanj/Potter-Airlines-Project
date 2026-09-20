"""Create a fresh SQLite database from the project's flight CSV.

Run: python database/init_db.py
Warning: rerunning replaces the database, including any seat changes.
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "potter_airline_routes_dataset_regenerated.csv"
DATABASE_PATH = Path(__file__).resolve().parent / "potter_airlines.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
FIELDS = (
    "flight_id", "origin", "destination", "flight_date", "departure_time",
    "route_popularity", "seat_capacity", "seats_remaining", "base_fare", "maximum_fare",
)


def main():
    # Validate the complete CSV before replacing an existing database.
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"Unexpected CSV columns: {reader.fieldnames}")
        rows = list(reader)

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.executescript(SCHEMA_PATH.read_text())
        connection.executemany(
            f"INSERT INTO flights ({', '.join(FIELDS)}) VALUES ({', '.join('?' for _ in FIELDS)})",
            ([row[field] for field in FIELDS] for row in rows),
        )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
        assert count == len(rows)
        print(f"Created {DATABASE_PATH} with {count} flights.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
