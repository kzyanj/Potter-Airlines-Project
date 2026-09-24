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

    def test_demo_cleans_up_if_pricing_fails(self):
        original = self.rows()
        with patch("backend.cli.calculate_price", side_effect=ValueError("pricing failed")):
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "pricing failed"):
                show_database_demo(datetime(2026, 9, 20))
        self.assertEqual(self.rows(), original)

    def test_invalid_dates_have_readable_errors(self):
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
        args = self.args.copy()
        args[args.index("--destination") + 1] = "Unknown"
        original = self.rows()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args + ["--demo-crud"]), 0)
        self.assertIn("No available future flights", output.getvalue())
        self.assertIn("DELETE:", output.getvalue())
        self.assertEqual(self.rows(), original)

    def test_limits_demo_without_search_results_does_not_modify_database(self):
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
