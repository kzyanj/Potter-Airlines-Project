"""Admin operations tested against a disposable SQLite database."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from backend.admin import add_flight, update_capacity
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
        """Create a valid flight and compare every stored field against the supplied data."""
        data = self.new_flight_data("PA-TEST-ADD")
        created = add_flight(data)
        stored = db.get_flight_by_id(created.flight_id)
        self.assertEqual(stored, tuple(data[field] for field in init_db.FIELDS))

    def test_update_capacity_preserves_other_fields(self):
        """Allow capacity increases, reductions to remaining seats, and repeated identical updates.
        Capacity equal to remaining seats is valid; every other field must remain unchanged."""
        data = self.new_flight_data("PA-TEST-CAPACITY")
        data.update(seat_capacity=100, seats_remaining=20)
        add_flight(data)
        before = db.get_flight_by_id(data["flight_id"])
        for capacity in (150, 20, 20):
            self.assertEqual(update_capacity(data["flight_id"], capacity), capacity)
            after = db.get_flight_by_id(data["flight_id"])
            self.assertEqual(after[6], capacity)
            self.assertEqual(after[:6] + after[7:], before[:6] + before[7:])

    def test_update_capacity_for_sold_out_flight(self):
        """Allow a sold-out flight to reduce capacity to the smallest positive integer, one.
        Changing capacity must not replenish remaining seats or remove the sold-out status."""
        data = self.new_flight_data("PA-TEST-SOLD-OUT-CAPACITY")
        data.update(seat_capacity=100, seats_remaining=0)
        add_flight(data)
        self.assertEqual(update_capacity(data["flight_id"], 1), 1)
        self.assertEqual(db.get_flight_by_id(data["flight_id"])[6:8], (1, 0))

    def test_invalid_capacity_does_not_change_flight(self):
        """Reject nonpositive or insufficient capacity, invalid types, and values beyond SQLite integer limits.
        Preserve the record after each failure and report missing flights."""
        data = self.new_flight_data("PA-TEST-INVALID-CAPACITY")
        data.update(seat_capacity=100, seats_remaining=20)
        add_flight(data)
        before = db.get_flight_by_id(data["flight_id"])
        for capacity in (0, -1, 19, 1.5, 100.0, True, False, "100", None,
                         float("nan"), float("inf"), 2 ** 63):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    update_capacity(data["flight_id"], capacity)
                self.assertEqual(db.get_flight_by_id(data["flight_id"]), before)
        with self.assertRaisesRegex(ValueError, "No flight found"):
            update_capacity("MISSING-FLIGHT", 100)

    def test_minimum_policy_rounding_and_rejects_old_percentage(self):
        """Round the 80% minimum fare to cents: a base of 100.03 produces 80.02.
        Reject the old 75% policy without inserting a record."""
        data = self.new_flight_data("PA-TEST-ROUNDING")
        data.update(base_fare=100.03, maximum_fare=200)
        data.pop("minimum_fare")
        self.assertEqual(add_flight(data).minimum_fare, 80.02)
        data["flight_id"] = "PA-TEST-OLD-POLICY"
        data["minimum_fare"] = 75.02
        with self.assertRaisesRegex(ValueError, "0.80"):
            add_flight(data)
        self.assertIsNone(db.get_flight_by_id(data["flight_id"]))

    def test_duplicate_id_is_rejected(self):
        """Reject a duplicate flight ID and translate the database uniqueness error into ValueError."""
        data = self.new_flight_data("PA-TEST-DUPLICATE")
        add_flight(data)
        with self.assertRaises(ValueError):
            add_flight(data)

    def test_delete_flight(self):
        """Return True when an existing flight is deleted and confirm it can no longer be retrieved.
        Deleting it again returns False instead of failing or affecting another record."""
        data = self.new_flight_data("PA-TEST-DELETE")
        add_flight(data)
        self.assertIsNotNone(db.get_flight_by_id(data["flight_id"]))
        self.assertTrue(db.delete_flight(data["flight_id"]))
        self.assertIsNone(db.get_flight_by_id(data["flight_id"]))
        self.assertFalse(db.delete_flight(data["flight_id"]))

    def test_minimum_fare_is_calculated_and_checked(self):
        """Calculate and persist the 80% minimum when minimum_fare is omitted.
        Reject an explicitly incorrect minimum without leaving a flight record behind."""
        data = self.new_flight_data("PA-TEST-MINIMUM")
        data.pop("minimum_fare")
        added = add_flight(data)
        self.assertEqual(added.minimum_fare, 104.00)
        self.assertEqual(db.get_flight_by_id(added.flight_id)[9], 104.00)
        invalid = self.new_flight_data("PA-TEST-WRONG-MINIMUM")
        invalid["minimum_fare"] = 100.00
        with self.assertRaises(ValueError):
            add_flight(invalid)
        self.assertIsNone(db.get_flight_by_id(invalid["flight_id"]))

    def test_invalid_base_fare_is_rejected(self):
        """Reject a missing base fare, nonnumeric text, and NaN.
        Failed creation attempts must not insert database records."""
        cases = (
            ("PA-TEST-NO-BASE", None),
            ("PA-TEST-TEXT-BASE", "not-a-number"),
            ("PA-TEST-NAN-BASE", float("nan")),
        )
        for flight_id, base_fare in cases:
            with self.subTest(flight_id=flight_id):
                data = self.new_flight_data(flight_id)
                data.pop("minimum_fare")
                if base_fare is None:
                    data.pop("base_fare")
                else:
                    data["base_fare"] = base_fare
                with self.assertRaises(ValueError):
                    add_flight(data)
                self.assertIsNone(db.get_flight_by_id(flight_id))

    def test_invalid_new_flight_is_rejected(self):
        """Reject creation when remaining seats exceed capacity and leave no invalid record behind."""
        data = self.new_flight_data("PA-TEST-INVALID")
        data["seats_remaining"] = data["seat_capacity"] + 1
        with self.assertRaises(ValueError):
            add_flight(data)
        self.assertIsNone(db.get_flight_by_id(data["flight_id"]))

    def test_noncanonical_date_or_time_is_rejected(self):
        """Require zero-padded dates and times, rejecting forms such as 2027-1-03 and 6:00.
        Consistent formatting supports correct string-based date queries and ordering."""
        for flight_id, field, value in (
            ("PA-TEST-DATE-FORMAT", "flight_date", "2027-1-03"),
            ("PA-TEST-TIME-FORMAT", "departure_time", "6:00"),
        ):
            with self.subTest(field=field):
                data = self.new_flight_data(flight_id)
                data[field] = value
                with self.assertRaises(ValueError):
                    add_flight(data)
                self.assertIsNone(db.get_flight_by_id(flight_id))

    def test_set_seats_persists_and_checks_capacity(self):
        """Persist an absolute seat count and reject negative counts or counts above capacity.
        Keep the previous valid count after rejection and report missing flights."""
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

    def test_seat_updates_reject_invalid_types_without_changing_data(self):
        """Require integers for absolute and relative updates; reject floats, booleans, text, None, NaN, and infinity.
        The entire flight record must remain unchanged after each rejected update."""
        flight_id = "PA000001"
        original = db.get_flight_by_id(flight_id)
        for update in (db.set_seats, db.update_seats):
            for value in (1.5, 1.0, True, False, "1", None, float("nan"), float("inf")):
                with self.subTest(operation=update.__name__, value=value):
                    with self.assertRaisesRegex(ValueError, "must be an integer"):
                        update(flight_id, value)
                    self.assertEqual(db.get_flight_by_id(flight_id), original)

    def test_update_seats_persists_and_checks_bounds(self):
        """Persist relative updates that reach exactly zero, make no change, or reach full capacity.
        Reject changes beyond either bound and updates to missing flights."""
        flight_id = "PA000001"
        capacity = db.get_flight_by_id(flight_id)[6]
        db.set_seats(flight_id, 1)
        for change, expected in ((-1, 0), (0, 0), (capacity, capacity)):
            self.assertEqual(db.update_seats(flight_id, change), expected)
            self.assertEqual(db.get_flight_by_id(flight_id)[7], expected)
        for change in (1, -(capacity + 1)):
            with self.assertRaises(ValueError):
                db.update_seats(flight_id, change)
            self.assertEqual(db.get_flight_by_id(flight_id)[7], capacity)
        with self.assertRaises(ValueError):
            db.update_seats("MISSING-FLIGHT", 1)

    def test_add_rejects_invalid_seats_and_nonfinite_fares_without_inserting(self):
        """Reject fractional or boolean seat counts and infinite or NaN fares through the admin entry point.
        Verify that failed requests do not insert a flight."""
        for field, value in (("seat_capacity", 100.5), ("seats_remaining", 1.5),
                             ("seats_remaining", True), ("maximum_fare", float("inf")),
                             ("maximum_fare", float("nan")), ("minimum_fare", float("inf"))):
            with self.subTest(field=field, value=value):
                data = self.new_flight_data("PA-TEST-BAD-NUMBER")
                data[field] = value
                with self.assertRaises(ValueError):
                    add_flight(data)
                self.assertIsNone(db.get_flight_by_id(data["flight_id"]))


class DatabaseInitializationTests(unittest.TestCase):
    def test_existing_database_survives_normal_run_and_failed_reset(self):
        """Prevent normal initialization from overwriting saved data and preserve edits when reset encounters bad CSV headers.
        Restore CSV data only when reset is explicit and the source CSV is valid."""
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
