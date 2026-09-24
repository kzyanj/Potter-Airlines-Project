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

# Potter Airlines Dynamic Revenue Management System

## 1. Project Overview

Potter Airlines is a Python application that calculates explainable, rule-based flight fares. Prices respond to six factors: route popularity, day of the week, departure time, remaining seat availability, seasonality, and days until departure. Each calculated fare is limited by the flight's minimum and maximum fare inputs before rounding to two decimal places.

The application imports fictional flight data into SQLite, searches for available flights by route and date, calculates fares across multiple flights with NumPy, ranks results, and demonstrates validated seat updates. The current runnable interface is a command-line application. The `frontend/` directory is a placeholder; a Streamlit interface is not included. No external API, LLM, or API key is required.

## 2. Installation and Quick Start

Use Python 3.10 or later. The only declared third-party dependency is `numpy>=1.24,<3`; SQLite support and the test framework come from Python's standard library. The current test suite was verified on Linux with Python 3.13.5 and NumPy 2.3.5.

Open a terminal in the extracted project folder, where `requirements.txt` is located, and run:

```bash
python -m pip install -r requirements.txt
python database/init_db.py
```

Initialization creates `database/potter_airlines.db` from the supplied CSV and imports 19,006 flights. The generated database is ignored by Git. If it already exists, initialization stops without overwriting it.

Run the complete command-line demonstration from the same project root:

```bash
python -m backend.cli --origin Toronto --destination Montreal --date 2026-10-02 --as-of 2026-09-20 --demo-pricing --demo-update
```

Use `python -m backend.cli`, not `python backend/cli.py`, so that the package imports resolve correctly. The fixed `--as-of` date makes this example reproducible even after the example flight date has passed.

To intentionally rebuild an existing database:

```bash
python database/init_db.py --reset
```

**Warning:** a successful reset replaces the database with the original CSV data. It discards saved seat changes and any flights added or deleted in SQLite. Normal runs should not use `--reset`.

## 3. Command-Line Usage and Demonstration

### Search options

```bash
python -m backend.cli --help
```

| Argument | Meaning |
| --- | --- |
| `--origin` | Required origin city, such as `Toronto`. |
| `--destination` | Required destination city, such as `Montreal`. |
| `--date` | Required departure date in `YYYY-MM-DD` format. |
| `--as-of` | Optional reference date for pricing and departure filtering. A supplied date is interpreted at midnight; omission uses the current local date and time. |
| `--demo-pricing` | Compare the first ranked flight at 45, 20, 7, and 1 calendar days before departure. |
| `--demo-update` | Temporarily reduce that flight's seat count by one, reject an invalid update, and restore the original count. |

Use city names as they appear in the dataset, including capitalization. Search results include only flights with seats remaining and a departure time later than the reference time. Results are sorted by fare, then departure time. Sold-out flights remain in SQLite but are excluded from search results and the available origin, destination, and date choices.

### Example results

With a freshly initialized, unmodified database, the quick-start command begins with:

```text
5 flights from Toronto to Montreal on 2026-10-02:
  PA000001  06:45  seats 79/180  fare 164.45
  PA000002  10:00  seats 77/180  fare 164.45
  PA000003  13:30  seats 62/180  fare 164.45
  PA000004  17:15  seats 42/180  fare 172.67
  PA000005  20:30  seats 76/180  fare 172.67
```

The application also reports the minimum, maximum, and average fare for the result set. For this example, the average is 167.74.

The pricing demonstration holds the flight's other inputs fixed and changes only the simulated search date. The seat-update demonstration changes `PA000001` from 79 to 78 seats, attempts an update that would make the count negative, prints the expected validation error, and restores 79 seats in a `finally` block. It demonstrates a database update rather than a permanent booking or an automatic repricing after the update.

### No matching flights

The supplied dataset starts on October 2, 2026. This valid search for an earlier date demonstrates an empty result:

```bash
python -m backend.cli --origin Toronto --destination Montreal --date 2026-10-01 --as-of 2026-09-20
```

```text
No available future flights match this search.
```

## 4. Project Structure and Design Choices

```text
Potter-Airlines-Project/
|-- backend/
|   |-- __init__.py
|   |-- flight.py          # Validated, immutable Flight model
|   |-- pricing.py         # Single-flight pricing and factor breakdown
|   |-- search.py          # Search helpers, vectorized fares, and ranking
|   |-- admin.py           # Validated flight creation
|   `-- cli.py             # Runnable search and demonstration workflow
|-- database/
|   |-- schema.sql         # flights table and database constraints
|   |-- init_db.py         # CSV import and explicit database reset
|   |-- db.py              # Connection management and CRUD operations
|   `-- potter_airlines.db # Generated during initialization
|-- data/
|   `-- potter_airline_routes_dataset_regenerated.csv
|-- tests/
|   |-- test_admin.py
|   |-- test_flight_pricing.py
|   `-- test_search.py
|-- frontend/              # Placeholder only
|-- requirements.txt
`-- README.md
```

`Flight` is a frozen dataclass representing one database record. It validates required fields, date and time formats, route popularity, seat ranges, and fare ordering. Its `departure` and `seat_fraction` properties provide the datetime and remaining-seat ratio used by pricing. Because a `Flight` object is a snapshot, it should be reloaded from SQLite after a seat update before recalculating its price.

Single-flight pricing is separated from storage and returns a `PriceResult` containing the final fare and all six multipliers. Search uses `analyze_fares()` to calculate a collection of fares with NumPy arrays, `np.where`, `np.select`, and `np.clip`. Python comprehensions prepare the arrays, but the factor selection and fare arithmetic are vectorized rather than implemented as repeated calls to the single-flight pricing function. Final result ordering uses Python's `sorted()`.

Database operations are kept in a separate module. SQL values are supplied through placeholders, including in queries whose fixed column lists or conditions are assembled in code. Connection handling commits successful transactions, rolls back failed transactions, and closes connections.

## 5. Flight Data and SQLite Persistence

The supplied CSV contains **19,006 scheduled flights**, covering **October 2, 2026 through October 2, 2027**. It connects Toronto, Montreal, Ottawa, and Vancouver through six city pairs, or twelve directional routes. The file includes sold-out flights as well as flights with available seats.

| Fields | Purpose |
| --- | --- |
| `flight_id` | Unique scheduled-flight identifier. |
| `origin`, `destination` | Departure and arrival city names. |
| `flight_date`, `departure_time` | Scheduled departure in `YYYY-MM-DD` and `HH:MM` format. |
| `route_popularity` | Fixed route-demand category: `Low`, `Medium`, or `High`. |
| `seat_capacity`, `seats_remaining` | Total capacity and currently available seats. |
| `base_fare`, `minimum_fare`, `maximum_fare` | Fare inputs and permitted bounds. |

`database/schema.sql` defines the `flights` table. Its constraints enforce different origin and destination cities, valid popularity categories, positive capacity, seats between zero and capacity, and `0 <= minimum_fare <= base_fare <= maximum_fare`. Initialization checks the CSV column names and order, imports through parameterized inserts, and asserts that the database row count matches the CSV. It stages the import in a temporary database before replacing the saved database, so an unsuccessful import does not overwrite saved data.

The persistence layer provides all four CRUD operations:

| Operation | Functions |
| --- | --- |
| Create | `backend.admin.add_flight()` validates a new flight and calls `database.db.insert_flight()`. |
| Read | `get_flight_by_id()`, `get_flights_by_destination()`, and the search functions retrieve records. |
| Update | `update_seats()` applies a change; `set_seats()` sets an exact integer count. |
| Delete | `delete_flight()` removes a record and reports whether a row was deleted. |

Administrative creation and deletion are Python functions, not command-line subcommands. They are exercised in `tests/test_admin.py`. Sold-out records can still be retrieved and updated through these backend functions.

Every supplied CSV record has a minimum fare equal to 75% of its base fare. `add_flight()` calculates this minimum with `Decimal` and `ROUND_HALF_UP`; a supplied minimum must match that rule. The lower-level database functions and schema enforce fare ordering, not the 75% policy itself. Calculated dynamic prices are not stored: they are recomputed when requested. SQLite changes do not modify the source CSV.

## 6. Pricing Logic

### Formula and fare limits

```python
from math import floor

# Use the flight's fare inputs and the calculated pricing factors.
raw_fare = (
    base_fare
    * route_factor
    * day_factor
    * time_of_day_factor
    * seats_factor
    * season_factor
    * days_until_flight_factor
)

bounded_fare = min(maximum_fare, max(minimum_fare, raw_fare))
price = floor(bounded_fare * 100 + 0.5 + 1e-9) / 100
```

The implementation applies the bounds before rounding. For the supplied cent-precision fare inputs, the result remains within the fare limits. The rounding expression rounds non-negative fares to the nearest cent, with a small tolerance for floating-point error.

### Implemented factors

Let `r = seats_remaining / seat_capacity`. Seat thresholds apply to this ratio without first rounding it to a whole percentage.

| Factor | Rules |
| --- | --- |
| Route popularity | Low: **0.95**; Medium: **1.00**; High: **1.10**. |
| Day of week | Monday-Friday: **1.00**; Saturday-Sunday: **1.05**. |
| Departure time | 21:00-05:59: **0.90**; 06:00-16:59: **1.00**; 17:00-20:59: **1.05**. |
| Seats remaining | `0 <= r <= 0.10`: **1.25**; `0.10 < r <= 0.20`: **1.10**; `0.20 < r <= 0.50`: **1.00**; `0.50 < r <= 1.00`: **0.95**. |
| Seasonality | Low: **0.90**; regular: **1.00**; peak: **1.10**; peak holiday: **1.20**. Dates are defined below. |
| Days until departure | 0-3 days: **1.30**; 4-14 days: **1.15**; 15-30 days: **1.00**; 31 or more days: **0.95**. |

Seasonality is determined by the departure date, with inclusive date boundaries:

| Season | Departure dates |
| --- | --- |
| Low | January 6-March 31 |
| Regular | April 1-June 14 and September 1-December 19 |
| Peak | June 15-August 31 |
| Peak holiday | December 20-January 5 |

Days until departure are calculated from calendar dates, not elapsed 24-hour periods. Today is day 0 and tomorrow is day 1. A flight departing at or before the reference datetime cannot be priced. The low-level pricing functions can calculate a hypothetical fare for zero remaining seats, but search excludes such flights; a calculated fare does not indicate ticket availability.

### Worked example

On a fresh database, `PA000001` departs Toronto for Montreal on Friday, October 2, 2026 at 06:45. It has 79 of 180 seats remaining, a base fare of 130.00, a minimum of 97.50, and a maximum of 235.00. With `--as-of 2026-09-20`, departure is 12 calendar days away.

```text
130.00 * 1.10 * 1.00 * 1.00 * 1.00 * 1.00 * 1.15 = 164.45
```

The route multiplier is 1.10, the weekday and departure-time multipliers are 1.00, the remaining-seat ratio is about 43.89%, the flight is in regular season, and the 12-day advance-booking multiplier is 1.15. The result is already between the fare limits, so the final fare is **164.45**.

## 7. Validation and Testing

Run the supplied tests from the project root:

```bash
python -m unittest discover -s tests -v
```

The current suite contains **19 test methods**, all of which passed in the verification environment listed above. Several methods exercise multiple boundary inputs using subtests.

| Test file | Coverage |
| --- | --- |
| `test_admin.py` | Flight creation and retrieval, duplicate IDs, deletion, the 75% minimum-fare rule, invalid new-flight data, seat setting, and preservation or reset of database contents. |
| `test_flight_pricing.py` | Model construction and properties, invalid fields, route/day/time/seat factors, season and advance-booking boundaries, fare limits, departed flights, and non-finite pricing inputs. |
| `test_search.py` | Available route/date choices, exclusion of sold-out or departed flights, ranking, empty results, invalid search filters, and agreement between vectorized and individual prices. |

Database tests use temporary database paths instead of modifying the normal project database. The command-line `--demo-update` option provides a visible checked edge case: an update below zero seats is rejected and the original seat count is restored. Passing the existing tests does not mean every possible input or operating condition has been covered.

## 8. Known Limitations

**Data and model scope.** The dataset is fictional and has a fixed date range. Route popularity, fare inputs, and multiplier thresholds are predefined rather than inferred from live demand. The model is not an optimization or machine-learning system. Departure datetimes have no timezone information; arrival times and aircraft types are not included. Use a fixed `--as-of` date to reproduce demonstrations after scheduled flights have passed.

**Interface and availability.** Only the command-line workflow and importable backend functions are implemented. There is no Streamlit interface, authentication, payment flow, booking system, or LLM/API integration. Sold-out flights are hidden from customer-facing search rather than displayed as unavailable. Some invalid command-line inputs raise exceptions without a friendly error message. The temporary update demonstration is not designed for concurrent booking activity.

**Input-validation gaps.** `set_seats()` requires an integer, but `update_seats()` and the `Flight` model do not consistently enforce integer seat inputs; a fractional update can currently be accepted. Fare inputs should use no more than two decimal places: the pricing functions clip before rounding, so a bound with additional decimal places can be crossed by the final rounding step. Direct database inserts also bypass some model-level validation. These are current limitations, not checks guaranteed by the existing tests.

**Maintenance.** Single-flight and vectorized pricing implement the same rules separately. Changes to multipliers or boundaries must be applied to both implementations and checked with tests. The declared NumPy version range is not a fully pinned environment, and the existing tests are not an exhaustive test suite.