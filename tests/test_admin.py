"""Admin operations tested against a disposable SQLite database."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from backend.admin import add_flight
from database import db, init_db


class AdminOperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.original_db_path = db.DATABASE_PATH
        cls.original_init_path = init_db.DATABASE_PATH
        test_path = Path(cls.temp_dir.name) / "test_flights.db"
        db.DATABASE_PATH = test_path
        init_db.DATABASE_PATH = test_path
        with redirect_stdout(io.StringIO()):
            init_db.main()

    @classmethod
    def tearDownClass(cls):
        db.DATABASE_PATH = cls.original_db_path
        init_db.DATABASE_PATH = cls.original_init_path
        cls.temp_dir.cleanup()

    def new_flight_data(self, flight_id):
        data = dict(zip(init_db.FIELDS, db.get_flight_by_id("PA000001")))
        data["flight_id"] = flight_id
        data["flight_date"] = "2027-10-03"
        return data

    def test_add_complete_flight(self):
        data = self.new_flight_data("PA-TEST-ADD")
        created = add_flight(data)
        stored = db.get_flight_by_id(created.flight_id)
        self.assertEqual(stored, tuple(data[field] for field in init_db.FIELDS))

    def test_duplicate_id_is_rejected(self):
        data = self.new_flight_data("PA-TEST-DUPLICATE")
        add_flight(data)
        with self.assertRaises(ValueError):
            add_flight(data)

    def test_minimum_fare_is_calculated_and_checked(self):
        data = self.new_flight_data("PA-TEST-MINIMUM")
        data.pop("minimum_fare")
        added = add_flight(data)
        self.assertEqual(added.minimum_fare, 97.50)
        self.assertEqual(db.get_flight_by_id(added.flight_id)[9], 97.50)
        invalid = self.new_flight_data("PA-TEST-WRONG-MINIMUM")
        invalid["minimum_fare"] = 100.00
        with self.assertRaises(ValueError):
            add_flight(invalid)
        self.assertIsNone(db.get_flight_by_id(invalid["flight_id"]))

    def test_invalid_new_flight_is_rejected(self):
        data = self.new_flight_data("PA-TEST-INVALID")
        data["seats_remaining"] = data["seat_capacity"] + 1
        with self.assertRaises(ValueError):
            add_flight(data)
        self.assertIsNone(db.get_flight_by_id(data["flight_id"]))

    def test_set_seats_persists_and_checks_capacity(self):
        flight_id = "PA000001"
        capacity = db.get_flight_by_id(flight_id)[6]
        self.assertEqual(db.set_seats(flight_id, 70), 70)
        self.assertEqual(db.get_flight_by_id(flight_id)[7], 70)
        for invalid in (-1, capacity + 1):
            with self.subTest(seats_remaining=invalid):
                with self.assertRaises(ValueError):
                    db.set_seats(flight_id, invalid)
                self.assertEqual(db.get_flight_by_id(flight_id)[7], 70)
        with self.assertRaises(ValueError):
            db.set_seats("MISSING-FLIGHT", 1)


class DatabaseInitializationTests(unittest.TestCase):
    def test_existing_database_survives_normal_run_and_failed_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            original_db_path = db.DATABASE_PATH
            original_init_path = init_db.DATABASE_PATH
            original_csv_path = init_db.CSV_PATH
            test_path = Path(temp) / "test_flights.db"
            db.DATABASE_PATH = test_path
            init_db.DATABASE_PATH = test_path
            try:
                with redirect_stdout(io.StringIO()):
                    init_db.main()
                original_seats = db.get_flight_by_id("PA000001")[7]
                db.set_seats("PA000001", 70)

                with self.assertRaises(FileExistsError):
                    init_db.main()
                self.assertEqual(db.get_flight_by_id("PA000001")[7], 70)

                bad_csv = Path(temp) / "bad.csv"
                bad_csv.write_text("wrong_header\ninvalid\n")
                init_db.CSV_PATH = bad_csv
                with self.assertRaises(ValueError):
                    init_db.main(reset=True)
                self.assertEqual(db.get_flight_by_id("PA000001")[7], 70)

                init_db.CSV_PATH = original_csv_path
                with redirect_stdout(io.StringIO()):
                    init_db.main(reset=True)
                self.assertEqual(db.get_flight_by_id("PA000001")[7], original_seats)
            finally:
                db.DATABASE_PATH = original_db_path
                init_db.DATABASE_PATH = original_init_path
                init_db.CSV_PATH = original_csv_path


if __name__ == "__main__":
    unittest.main()
