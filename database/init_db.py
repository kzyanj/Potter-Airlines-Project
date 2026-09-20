"""Initialize SQLite from the flight CSV once, preserving later database edits.

Run: python database/init_db.py
Use --reset only when you intentionally want to discard SQLite changes.
"""

import argparse
import csv
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "potter_airline_routes_dataset_regenerated.csv"
DATABASE_PATH = Path(__file__).resolve().parent / "potter_airlines.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
FIELDS = (
    "flight_id", "origin", "destination", "flight_date", "departure_time",
    "route_popularity", "seat_capacity", "seats_remaining", "base_fare", "minimum_fare", "maximum_fare",
)


def main(reset=False):
    """Create the database; require an explicit reset to replace one that exists."""
    if DATABASE_PATH.exists() and not reset:
        raise FileExistsError(
            f"Database already exists at {DATABASE_PATH}. "
            "Use --reset only if you want to discard saved flight and seat changes."
        )

    with CSV_PATH.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"Unexpected CSV columns: {reader.fieldnames}")
        rows = list(reader)

    # Import into a temporary database first. A failed import leaves the saved
    # database untouched, even when --reset was requested.
    with tempfile.TemporaryDirectory(dir=DATABASE_PATH.parent) as temp_dir:
        staged_path = Path(temp_dir) / DATABASE_PATH.name
        connection = sqlite3.connect(staged_path)
        try:
            connection.executescript(SCHEMA_PATH.read_text())
            connection.executemany(
                f"INSERT INTO flights ({', '.join(FIELDS)}) VALUES ({', '.join('?' for _ in FIELDS)})",
                ([row[field] for field in FIELDS] for row in rows),
            )
            connection.commit()
            count = connection.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
            assert count == len(rows)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        staged_path.replace(DATABASE_PATH)
    print(f"Created {DATABASE_PATH} with {count} flights.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the Potter Airlines SQLite database")
    parser.add_argument("--reset", action="store_true", help="Replace an existing database from the CSV")
    args = parser.parse_args()
    try:
        main(reset=args.reset)
    except FileExistsError as error:
        parser.exit(1, f"{error}\n")
