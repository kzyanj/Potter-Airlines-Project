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
| `--demo-pricing` | Show five booking dates for the first result, plus fixed minimum/maximum fare examples. |
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
   Medium popularity, a base fare of 100, a minimum of 80, and a maximum of 500.
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
the five-booking-date comparison is skipped, but the fixed fare-limit examples
and `--demo-crud` still run when requested.

### Fare-limit examples

`--demo-pricing` also runs two fixed examples in memory. These use simulated
booking dates, work regardless of today's date, and do not change SQLite.
Both have base fare 100, minimum fare 80, and an illustrative maximum fare 150.
The maximum is configured per flight, not a universal 150%-of-base rule.

| Example | Inputs | Before limits | Final fare |
| --- | --- | --- | --- |
| Minimum | Feb 20, 2027 departure; 90 days ahead; Low popularity; 100/100 seats | `100 × 0.97 × 0.92 × 0.90 × 0.95 = 76.3002` | 80.00 |
| Maximum | Dec 20, 2026 departure; 1 day ahead; High popularity; 1/100 seats | `100 × 1.06 × 1.30 × 1.25 × 1.30 = 223.925` | 150.00 |

The CLI prints the inputs and factor breakdown, followed by:

```text
Calculated fare: 76.30 → Minimum fare applied: 80.00
Calculated fare: 223.93 → Maximum fare applied: 150.00
```

The displayed calculated fare is formatted to two decimals; the engine applies
limits to the unrounded amount before rounding the final fare. Assertions verify
that each example crosses its intended limit and returns that limit.

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

## Pricing factors

```text
raw fare = base fare × route factor × seats factor × season factor × days factor
final fare = round to cents(min(maximum fare, max(minimum fare, raw fare)))
```

Multipliers below 1 discount the fare; above 1 increase it. There are four
factors; weekday and time of day do not add separate multipliers. Minimum fare
is 80% of base fare, rounded half-up to cents; maximum fare is stored per flight.
Final fares are also rounded half-up to cents.

| Factor | Category / range | Multiplier |
| --- | --- | --- |
| Route Popularity | Low | 0.97× |
| Route Popularity | Medium | 1.00× |
| Route Popularity | High | 1.06× |
| Seats Remaining | Very High: >65–100% | 0.92× |
| Seats Remaining | High: >40–65% | 0.97× |
| Seats Remaining | Moderate: >20–40% | 1.05× |
| Seats Remaining | Low: >10–20% | 1.15× |
| Seats Remaining | Very Low: >5–10% | 1.22× |
| Seats Remaining | Critical: >0–5% | 1.30× |
| Seats Remaining | Sold Out: 0% | No ticket available |
| Seasonality | Low Season | 0.90× |
| Seasonality | Regular Season | 1.00× |
| Seasonality | Peak Season | 1.12× |
| Seasonality | Peak Holiday | 1.25× |
| Days Until Flight | Very Early: 61+ days | 0.95× |
| Days Until Flight | Standard: 31–60 days | 1.00× |
| Days Until Flight | Near Term: 15–30 days | 1.05× |
| Days Until Flight | Soon: 4–14 days | 1.15× |
| Days Until Flight | Last Minute: 0–3 days | 1.30× |

Seat percentages use the actual ratio of remaining seats to capacity, without
rounding. For example, >5–10% means greater than 5% and at most 10%; 5.5% uses
1.22×. These continuous ranges include the original whole-percent bands such
as 6–10%, while avoiding gaps for fractional percentages. Sold-out flights are
excluded from search, and direct pricing of one raises an error.

| Season | Departure dates (both endpoints included, repeated yearly) |
| --- | --- |
| Low Season | January 6–March 31 and November 1–December 19 |
| Regular Season | April 1–June 24 and September 1–October 31 |
| Peak Season | June 25–August 31 |
| Peak Holiday | December 20–January 5 (across New Year) |

Days until flight uses calendar-date differences: today is day 0, tomorrow is
day 1. Flights that have already departed, including departures exactly at the
search time, cannot be priced or returned as available results.

## Run tests

```bash
python -m unittest discover -s tests -v
```

Tests cover flight validation, pricing boundaries, scalar/vectorized pricing
agreement, fare limits, filtering and ranking, database operations, and CLI
workflows. CLI tests check the expected output, readable errors, and cleanup
after a simulated pricing failure. Database tests use temporary databases rather
than modifying `database/potter_airlines.db`.

The minimum fare is **80% of base fare**, rounded to two decimal places using
half-up rounding. New flights and the source CSV use this rule. The strongest
combined discount produces about 76.3% of base fare, so the minimum raises that
fare to 80%.

For a database created before this change, synchronize minimum fares without
resetting saved flights or seat counts:

```bash
python -m database.migrate_minimum_fares
```

This updates only `minimum_fare` for existing flights and can be run again safely.
Fresh databases created from the updated CSV already use 80%.

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
