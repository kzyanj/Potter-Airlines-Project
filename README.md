# Potter Airlines Dynamic Revenue Management System

A Python project for calculating explainable flight prices from time to departure,
route demand, remaining seats, and seasonality. The backend includes SQLite
persistence, vectorized NumPy pricing, and a runnable command-line workflow.

## Project structure

```text
data/       Source flight CSV
database/   SQLite schema, data import, and database operations (Backend)
backend/    Flight class, pricing, filtering, ranking, and CLI
frontend/   Streamlit interface (to be built)
tests/      Database, pricing, search, validation, and CLI tests
README.md   Setup, project progress, and final documentation
```

The three work areas are **Backend**, **Frontend**, and **Testing**.
Deliverables are tracked separately below; they do not need a code folder.

## Current data and database (Backend)

- `data/potter_airline_routes_dataset_regenerated.csv` is the source data. Each
  row is one scheduled flight with a unique ID, origin, destination, date,
  departure time, route popularity, seat capacity, remaining seats, base fare,
  and maximum fare. Origins and destinations are city names such as `Toronto`.
- `database/schema.sql` defines the `flights` table.
- `database/init_db.py` imports the CSV into SQLite and validates the row count.
- `database/db.py` provides parameterized flight lookup, insertion, deletion,
  and seat updates with capacity checks.

The dataset has no arrival times or aircraft types. Database changes do not
modify the source CSV.

## Setup

Use Python 3.10 or newer. From the project root, run:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python database/init_db.py
```

This creates `database/potter_airlines.db`, which is ignored by Git. If the
database already exists, this command stops without changing it. **Only run
`python database/init_db.py --reset` when you intentionally want to rebuild
the database from the CSV; resetting erases saved flight edits and seat changes.**

On Windows, activate the environment with `.venv\Scripts\activate` instead.
SQLite uses Python's standard library; NumPy is installed from `requirements.txt`.
No API keys or external services are required.

## Command-line interface (CLI)

CLI means **Command-Line Interface**: run the system by entering commands in a
terminal. Run the commands below from the project root with the environment
activated. Use `python -m backend.cli --help` to see all options.

### Search flights

```bash
python -m backend.cli --origin Toronto --destination Montreal \
  --date 2026-10-02 --as-of 2026-09-20
```

| Argument | Purpose |
| --- | --- |
| `--origin` | Required origin city, matching the dataset spelling. |
| `--destination` | Required destination city; must differ from origin. |
| `--date` | Required departure date in `YYYY-MM-DD` format. |
| `--as-of` | Optional simulated search date at midnight. Without it, the current local date and time are used. |
| `--demo-pricing` | Show the first search result's fare at five simulated booking dates. |
| `--demo-crud` | Demonstrate INSERT, SELECT, UPDATE, and DELETE using a temporary flight. |
| `--demo-update` | Alias for `--demo-crud`; runs the same complete database demonstration. |

The search reads matching flights from SQLite, excludes sold-out and departed
flights, and calculates fares in batches with NumPy. Results are sorted by fare
ascending, then departure time. Output includes each flight's ID, departure time,
remaining seats/capacity, and fare, followed by the minimum, maximum, and average
fare across the results. Those summary minimum/maximum values describe the
results, rather than each flight's configured fare limits.

Use the fixed `--as-of` above to reproduce the example even after the flight date
has passed in real time. Actual search results depend on saved database edits.
If there are no matches, the program prints
`No available future flights match this search.`

### Run the complete demonstration

```bash
python -m backend.cli --origin Toronto --destination Montreal \
  --date 2026-10-02 --as-of 2026-09-20 \
  --demo-pricing --demo-crud
```

After the search results, the program runs these demonstrations:

1. **Pricing changes over time:** Keep the first result's departure date, route,
   and remaining seats fixed. Simulate booking 90, 45, 20, 7, and 1 day before
   departure. Print the base fare, all four multipliers, and the final bounded
   fare for each scenario. The days-until-flight multipliers are respectively
   0.95, 1.00, 1.05, 1.15, and 1.30. Seasonality uses the departure date, so it
   stays fixed. Fare limits can cause different scenarios to produce the same
   final price. This demonstration does not save price changes.
2. **INSERT and SELECT:** Create a uniquely named `DEMO-...` flight from Toronto
   to Montreal, departing 45 days after `--as-of`. It has 100 seats, 21 remaining,
   Medium popularity, a base fare of 100, a minimum of 75, and a maximum of 500.
   Read it back from SQLite and calculate its fare. This is a separate example
   flight, not one of the search results.
3. **UPDATE and reprice:** Reduce its remaining seats from 21 to 20. Read the
   updated row into a new `Flight` object and calculate the fare again. The seat
   multiplier changes from 1.05 to 1.15; the other factors remain unchanged.
4. **Checked edge case:** Attempt to remove another 21 seats, which would leave
   -1 seat. Catch the expected error and assert that the saved count remains 20.
5. **DELETE and verify:** Delete the temporary flight and assert that it no
   longer exists. Cleanup also runs if a later demo step raises an exception.
   Existing flights and the source CSV are unchanged.

For `--as-of 2026-09-20`, the temporary flight departs on November 4 (Low Season).
Its fare changes from `100 × 1.00 × 1.05 × 0.90 × 1.00 = 94.50` to
`100 × 1.00 × 1.15 × 0.90 × 1.00 = 103.50`. The database portion prints:

```text
INSERT: temporary flight DEMO-<unique ID>
SELECT: seats 21/100, fare 94.50
UPDATE: seats 21 → 20; seat factor 1.05 → 1.15; fare 94.50 → 103.50
Expected invalid update rejected: Seats must stay between 0 and 100
DELETE: temporary flight removed; existing flights unchanged.
```

The unique ID changes on every run. Changing `--as-of` can change the season and
therefore the demonstration's prices. If a search returns no matches,
`--demo-pricing` is skipped, but `--demo-crud` still runs.

### Errors and checks

Invalid or noncanonical dates such as `2026-02-30` or `2026-9-20` produce a
`Use a valid date in YYYY-MM-DD format` message and exit status 2. Missing
required arguments also use status 2. Expected runtime errors, such as identical
origin/destination or an uninitialized database, print `Error: ...` and return
status 1. Successful runs, including searches with no matches, return status 0.
The intentionally rejected seat update is a successful demonstration of a check,
not a failed command. Run without Python's `-O` option so demo assertions execute.

If the database is missing, run `python database/init_db.py`. If NumPy is missing,
install dependencies with `python -m pip install -r requirements.txt`.

## Run tests

```bash
python -m unittest discover -s tests -v
```

Tests cover flight validation, pricing boundaries, scalar/vectorized pricing
agreement, fare limits, filtering and ranking, database operations, and CLI
workflows. CLI tests check the expected output, readable errors, and cleanup
after a simulated pricing failure. Database tests use temporary databases rather
than modifying `database/potter_airlines.db`.

The administrator's minimum-fare rule remains **75% of base fare**. A pricing
engine test uses a custom 80% lower bound to exercise clamping; this does not
change the rule for newly added flights or the source data.

## Project task tracker

### Backend

- [x] Add the supplied flight dataset and SQLite schema.
- [x] Import flights and provide parameterized database operations.
- [x] Validate flight IDs and seat limits during import or updates.

- [x] Add a meaningful `Flight` class and pricing functions.
- [x] Define explainable factors for time to departure, route demand, seat
      availability, and seasonality; keep prices within sensible minimum and
      maximum bounds.
- [x] Calculate prices for multiple flights and filter or rank useful results.
- [x] Use Pandas or NumPy vectorized operations for at least one meaningful
      calculation or analysis across multiple flights.
- [x] Add assertions and handle pricing edge cases.

### Frontend

- [ ] Build a Streamlit interface.
- [ ] Add origin, destination, and departure date selection.
- [ ] Show flights and calculated prices; allow flight selection.
- [ ] Provide a control to update and display remaining seats.

### Testing

- [x] Test database SELECT, INSERT, UPDATE, and DELETE operations.
- [x] Test pricing boundaries and minimum/maximum fare rules.
- [x] Test invalid seat counts and capacity limits.
- [x] Test flight filtering, ranking, and seat updates through the CLI.
- [ ] Test the planned Streamlit interface when implemented.
- [x] Demonstrate at least one checked edge case.

### Deliverables

- [ ] Document the final pricing logic, setup, run steps, design choices, and
      known limitations here.
- [x] Provide a runnable interaction or script workflow.
- [ ] Record a 4–5 minute demo showing the program, a pricing decision,
      meaningful code, and a checked edge case.

The project specification accepts a command-line or script workflow; Streamlit
is the team's planned frontend, not a specification requirement. LLM/API use
and advanced optimization are optional. A connecting-flight search is not required.
