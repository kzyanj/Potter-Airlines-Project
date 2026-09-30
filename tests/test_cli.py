"""CLI workflows use a disposable database and leave existing flights intact."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from backend.cli import main, show_database_demo
from database import db


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "cli.db"
        patcher = patch.object(db, "DATABASE_PATH", self.database)
        patcher.start()
        self.addCleanup(patcher.stop)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.executescript((Path(__file__).resolve().parents[1] / "database/schema.sql").read_text())
        for flight_id, seats in (("CLI-A", 60), ("CLI-B", 20)):
            db.insert_flight(dict(
                flight_id=flight_id, origin="Toronto", destination="Montreal",
                flight_date="2026-10-02", departure_time="12:00", route_popularity="Medium",
                seat_capacity=100, seats_remaining=seats, base_fare=100.0,
                minimum_fare=80.0, maximum_fare=250.0,
            ))
        self.args = ["--origin", "Toronto", "--destination", "Montreal",
                     "--date", "2026-10-02", "--as-of", "2026-09-20"]

    def rows(self):
        with db.get_connection() as connection:
            return connection.execute("SELECT * FROM flights ORDER BY flight_id").fetchall()

    def test_complete_workflow_and_legacy_update_option(self):
        """Run search, pricing, creation, retrieval, update, invalid-update rejection, and temporary-flight deletion.
        Check both demo flags, readable boundary/change output, and preservation of existing records."""
        original = self.rows()
        for flag in ("--demo-crud", "--demo-update"):
            with self.subTest(flag=flag):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(self.args + ["--demo-pricing", flag]), 0)
                text = output.getvalue()
                for expected in ("2 flights", "90 days before", "INSERT:", "SELECT:",
                                 "seat factor 1.05 → 1.15", "fare 94.50 → 103.50",
                                 "Expected invalid update rejected", "DELETE:",
                                 "Calculated fare: 76.30 → Minimum fare applied: 80.00",
                                 "Calculated fare: 223.93 → Maximum fare applied: 150.00"):
                    self.assertIn(expected, text)
                self.assertEqual(self.rows(), original)

    def test_sold_out_results_and_pricing_demo(self):
        """Check CLI output for partly and completely sold-out results.
        When all flights are sold out, retain flight listings but skip fare statistics and selected-flight pricing."""
        db.set_seats("CLI-B", 0)
        for all_sold in (False, True):
            with self.subTest(all_sold=all_sold):
                if all_sold:
                    db.set_seats("CLI-A", 0)
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(self.args + ["--demo-pricing"]), 0)
                text = output.getvalue()
                self.assertIn("2 flights", text)
                self.assertIn("CLI-B  12:00  seats 0/100  Sold out", text)
                if all_sold:
                    self.assertNotIn("Fare range:", text)
                    self.assertNotIn("Simulated fare calculation for", text)
                else:
                    self.assertIn("Fare range: 111.55–111.55; average: 111.55", text)

    def test_demo_cleans_up_if_pricing_fails(self):
        """Patch pricing to raise an exception and verify finally still removes the temporary demo flight.
        Existing records must remain unchanged after the failed demonstration."""
        original = self.rows()
        with patch("backend.cli.calculate_price", side_effect=ValueError("pricing failed")):
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "pricing failed"):
                show_database_demo(datetime(2026, 9, 20))
        self.assertEqual(self.rows(), original)

    def test_invalid_dates_have_readable_errors(self):
        """Pass impossible dates, noncanonical dates, and arbitrary text to --date and --as-of.
        Expect argument-parser exit code 2 and a readable format message without a traceback."""
        for flag in ("--date", "--as-of"):
            for value in ("2026-02-30", "2026-9-20", "bad-date"):
                args = self.args.copy()
                args[args.index(flag) + 1] = value
                output = io.StringIO()
                with redirect_stderr(output), self.assertRaises(SystemExit) as error:
                    main(args)
                self.assertEqual(error.exception.code, 2)
                self.assertIn("valid date in YYYY-MM-DD format", output.getvalue())
                self.assertNotIn("Traceback", output.getvalue())

    def test_missing_database_and_invalid_route(self):
        """Return CLI error code 1 for a missing database or identical origin and destination.
        Show a readable Error message rather than a traceback."""
        for missing in (False, True):
            output = io.StringIO()
            args = self.args.copy()
            if not missing:
                args[args.index("--destination") + 1] = "Toronto"
            path = Path(self.temp.name) / "missing.db" if missing else self.database
            with patch.object(db, "DATABASE_PATH", path), redirect_stderr(output):
                self.assertEqual(main(args), 1)
            self.assertIn("Error:", output.getvalue())
            self.assertNotIn("Traceback", output.getvalue())

    def test_no_results_still_allows_crud_demo(self):
        """Allow the create/read/update/delete demonstration even when the destination has no results.
        Check the empty-result message, temporary-flight cleanup, and unchanged existing records."""
        args = self.args.copy()
        args[args.index("--destination") + 1] = "Unknown"
        original = self.rows()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args + ["--demo-crud"]), 0)
        self.assertIn("No future flights", output.getvalue())
        self.assertIn("DELETE:", output.getvalue())
        self.assertEqual(self.rows(), original)

    def test_limits_demo_without_search_results_does_not_modify_database(self):
        """Demonstrate minimum and maximum fares with fixed in-memory examples when search returns nothing.
        Skip selected-flight pricing and leave database contents unchanged."""
        args = self.args.copy()
        args[args.index("--destination") + 1] = "Unknown"
        original = self.rows()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args + ["--demo-pricing"]), 0)
        self.assertIn("Minimum fare applied: 80.00", output.getvalue())
        self.assertIn("Maximum fare applied: 150.00", output.getvalue())
        self.assertNotIn("Simulated fare calculation for", output.getvalue())
        self.assertEqual(self.rows(), original)
