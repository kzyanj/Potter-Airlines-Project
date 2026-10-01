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

The search reads matching flights from SQLite, excludes departed
flights, and calculates fares in batches with NumPy. Results are sorted by fare
ascending, then departure time. Sold-out flights appear last with zero remaining
seats and `Sold out`, and their search result price is `None`. Fare statistics
include only flights with seats remaining. Output includes each flight's ID, departure time,
remaining seats/capacity, and fare, followed by the minimum, maximum, and average
fare across the results. Those summary minimum/maximum values describe the
results, rather than each flight's configured fare limits.

Use the fixed `--as-of` above to reproduce the example even after the flight date
has passed in real time. Actual search results depend on saved database edits.
If there are no matches, the program prints
`No future flights match this search.`

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

Databases initialized from the current CSV already use the 80% minimum-fare rule.

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

Potter Airlines is a Python application for explainable, rule-based flight pricing and seat-inventory management. It calculates fares using four factors: route popularity, remaining seats, seasonality, and days until departure. The calculated amount is constrained by each flight's minimum and maximum fares before rounding to two decimal places.

The project includes a Streamlit administrator interface, a command-line interface, SQLite persistence, a validated `Flight` class, and NumPy-based pricing across multiple flights. Administrators can search flights, compare fares, and update remaining seats to observe the effect on pricing. This is a revenue-management demonstration, not a customer booking or payment system. No external API, LLM, or API key is required.

## 2. Setup and Running the Application

Use Python 3.10 or later. The declared third-party dependencies are `numpy>=1.24,<3` and `streamlit>=1.30,<2`. SQLite support and `unittest` are provided by Python's standard library.

Open a terminal in the project root, which contains `backend/`, `database/`, `frontend/`, and `requirements.txt`. Install the dependencies and initialize the database:

```bash
python -m pip install -r requirements.txt
python database/init_db.py
```

Initialization imports the supplied CSV into `database/potter_airlines.db`. If the database already exists, the command stops without overwriting it. Initialize the database before launching either interface.

To launch the Streamlit administrator interface:

```bash
streamlit run frontend/app.py
```

To run the complete command-line demonstration:

```bash
python -m backend.cli --origin Toronto --destination Montreal --date 2026-10-02 --as-of 2026-09-20 --demo-pricing --demo-crud
```

Run the CLI as a module from the project root rather than executing `backend/cli.py` directly. The fixed `--as-of` date makes the example reproducible even after its departure date has passed in real time.

### Rebuilding the database

To deliberately replace SQLite with the current CSV contents:

```bash
python database/init_db.py --reset
```

**Warning:** this removes database-only additions and edits and can restore flights previously deleted from SQLite. It is not necessarily a return to the original seat inventory: seat updates may already have been synchronized to the CSV. Back up both the database and CSV before demonstrations that modify existing flights.

## 3. Using the Application and Demonstrations

### Streamlit administrator workflow

Select an origin, destination, and departure date. The date picker allows any date between October 2, 2026 and October 2, 2027, including route/date combinations with no scheduled flights. Searches use the current local date and time; the interface does not provide an as-of date control.

The results table displays flight identifiers, cities, departure dates and times, seats remaining, capacity, fare, and availability status. Results can be ordered by price or departure time. In price order, available flights appear first and sold-out flights appear last. In departure-time order, all returned flights follow their scheduled departure times.

In the administrator section, select a flight, enter an exact integer seat count, and press **Update seats**. The backend validates the count, saves it, and reloads the flight to calculate its updated fare. The results table is queried again after the update. A fare may remain unchanged when the update stays within the same pricing band or when a fare limit applies.

Setting the count to zero displays `SOLD OUT` rather than a price. The flight remains selectable, and restoring a positive count makes it priceable again. A value above capacity is rejected with an error message. When no flights match, the interface displays: "No flights available for the selected route and date."

### Command-line options

`--origin` and `--destination` specify different city names using the dataset's spelling and capitalization. `--date` specifies the departure date in `YYYY-MM-DD` format. `--as-of` optionally supplies a reference date at midnight; omission uses the current local date and time.

`--demo-pricing` compares the first available, price-ranked flight at 90, 45, 20, 7, and 1 day before departure. It also runs fixed minimum- and maximum-fare examples in memory. Those examples do not modify the database and still run when the search has no matches.

`--demo-crud` creates a uniquely named temporary flight, retrieves it, reduces its seats from 21 to 20, recalculates its price, rejects an update that would produce negative seats, and deletes the temporary record. `--demo-update` is an alias for this same demonstration; it no longer modifies an existing search-result flight.

With `--as-of 2026-09-20`, the temporary flight departs on November 4, 2026. Reducing its seats from 21% to 20% changes the seat multiplier from 1.05 to 1.15 and the fare from 94.50 to 103.50. Cleanup removes the temporary record even if a later demonstration step raises an exception. Existing flights and the source CSV remain unchanged by this temporary-flight demonstration.

For help:

```bash
python -m backend.cli --help
```

### Reproducible edge-case searches

The supplied data has no Montreal-to-Ottawa flights on November 17, 2026:

```bash
python -m backend.cli --origin Montreal --destination Ottawa --date 2026-11-17 --as-of 2026-09-20
```

The CLI prints:

```text
No future flights match this search.
```

The following search includes the supplied sold-out flight `PA000009`:

```bash
python -m backend.cli --origin Toronto --destination Ottawa --date 2026-10-02 --as-of 2026-09-20
```

Sold-out flights have price `None` internally, appear with a sold-out label, and are excluded from numerical fare statistics. These examples assume the supplied records have not been changed.

## 4. Project Structure and Design Choices

`backend/flight.py` defines the frozen `Flight` dataclass. It validates required fields, different origin and destination cities, canonical date/time formats, popularity categories, integer seat counts, finite fare values, and valid ranges. Its `departure` and `seat_fraction` properties support pricing. A `Flight` is a snapshot of a record, so it must be reloaded after a database change.

`backend/pricing.py` contains the shared route multipliers, seat and booking-day bands, seasonal helper, and single-flight calculation. `PriceResult` contains the final fare and the four applied multipliers, supporting an explanation of each pricing decision.

`backend/search.py` handles route/date choices, flight filtering, batch pricing, and ranking. `analyze_fares()` uses NumPy arrays, `np.select`, `np.clip`, and element-wise arithmetic to calculate multiple fares. Array preparation still uses Python comprehensions, and result ordering uses Python sorting. Both pricing paths use the shared rules from `pricing.py` rather than maintaining separate copies of the multiplier tables.

`backend/admin.py` provides validated flight creation and capacity updates. Capacity updates preserve remaining seats and reject capacities below that count. These administrative functions are available through Python; the Streamlit interface exposes remaining-seat updates, not flight creation, deletion, or capacity editing. `backend/cli.py` provides the runnable command-line workflow and demonstrations.

`frontend/app.py` handles controls and display. It calls backend functions rather than calculating fares or issuing SQL itself. `database/schema.sql` defines the table, `database/init_db.py` imports the CSV, `database/db.py` implements database operations and seat synchronization. The `data/` directory contains the CSV; `tests/` contains model, pricing, database, search, and CLI tests.

## 5. Flight Data and Persistence

The supplied CSV contains **19,006 scheduled flights** from October 2, 2026 through October 2, 2027. It connects Toronto, Montreal, Ottawa, and Vancouver through six city pairs, or twelve directional routes. Some route/date combinations have no records, and some flights have zero seats remaining.

Each record contains eleven fields: `flight_id`, `origin`, `destination`, `flight_date`, `departure_time`, `route_popularity`, `seat_capacity`, `seats_remaining`, `base_fare`, `minimum_fare`, and `maximum_fare`. Arrival times, aircraft types, and timezone information are not included.

SQLite supports create, read, update, and delete operations using parameterized values. The schema enforces different origin and destination cities, valid popularity categories, positive capacity, seats within capacity, and `minimum_fare <= base_fare <= maximum_fare` with a non-negative minimum. Initialization checks the CSV header and imported row count. It builds a temporary database before replacing the saved database, protecting existing data when import fails.

`add_flight()` validates and inserts a new flight. `get_flight_by_id()`, `get_flights_by_destination()`, and search helpers retrieve records. `update_seats()` applies a relative change, while `set_seats()` sets an absolute count. `set_capacity()`, exposed through `backend.admin.update_capacity()`, changes capacity without changing remaining seats. `delete_flight()` removes a record.

SQLite is the primary operational store. For matching records in the supplied CSV, updates through `set_seats()` and `update_seats()` also synchronize `seats_remaining` after the default database transaction commits. Synchronization is skipped for temporary databases, a missing CSV, or records not present in the CSV. Other operations, including flight creation, deletion, capacity changes, and minimum-fare migration, do not rewrite the CSV.

Every supplied record uses `minimum_fare = 0.80 * base_fare`. `add_flight()` calculates this minimum with `Decimal` and `ROUND_HALF_UP` and rejects a conflicting supplied minimum. The lower-level schema enforces fare ordering rather than the 80% policy. Dynamic fares are calculated when requested rather than stored in SQLite.

## 6. Pricing Logic

### Formula and fare limits

The implemented formula can be expressed as:

```python
raw_fare = (
    base_fare
    * route_factor
    * seats_factor
    * season_factor
    * days_until_flight_factor
)

bounded_fare = min(maximum_fare, max(minimum_fare, raw_fare))
```

The raw amount is limited to the flight's configured minimum and maximum, then rounded to cents. Weekday/weekend and departure time do not apply separate multipliers. Departure time still determines whether a flight has already departed.

### Route popularity

| Popularity | Multiplier |
| --- | --- |
| Low | 0.97 |
| Medium | 1.00 |
| High | 1.06 |

### Remaining seats

Let `r = seats_remaining / seat_capacity`. The ratio is used without rounding the percentage.

| Remaining-seat ratio | Multiplier or status |
| --- | --- |
| `0.65 < r <= 1.00` | 0.92 |
| `0.40 < r <= 0.65` | 0.97 |
| `0.20 < r <= 0.40` | 1.05 |
| `0.10 < r <= 0.20` | 1.15 |
| `0.05 < r <= 0.10` | 1.22 |
| `0.00 < r <= 0.05` | 1.30 |
| `r = 0` | Sold out; no fare |

Zero seats means sold out, not a zero-price ticket. Direct single-flight and batch pricing reject sold-out flights; search retains them separately without a fare.

### Seasonality

| Season | Departure dates | Multiplier |
| --- | --- | --- |
| Low Season | January 6-March 31 and November 1-December 19 | 0.90 |
| Regular Season | April 1-June 24 and September 1-October 31 | 1.00 |
| Peak Season | June 25-August 31 | 1.12 |
| Peak Holiday | December 20-January 5 | 1.25 |

All endpoints are inclusive, and the seasonal rules repeat annually based on the departure date.

### Days until departure

| Category | Calendar days until departure | Multiplier |
| --- | --- | --- |
| Very Early | 61 or more | 0.95 |
| Standard | 31-60 | 1.00 |
| Near Term | 15-30 | 1.05 |
| Soon | 4-14 | 1.15 |
| Last Minute | 0-3 | 1.30 |

The difference is measured in calendar dates rather than completed 24-hour periods. A flight departing at or before the reference datetime cannot be priced or returned by search.

### Worked example

In the supplied updated CSV, `PA000001` departs Toronto for Montreal on October 2, 2026 at 06:45. It has 180 of 180 seats remaining, High popularity, a base fare of 130.00, a minimum of 104.00, and a maximum of 235.00. With `--as-of 2026-09-20`, the flight is 12 calendar days away:

```text
130.00 * 1.06 * 0.92 * 1.00 * 1.15 = 145.7924
```

The amount is within the fare limits, producing a final fare of **145.79**. This example changes if the saved seat inventory changes.

### Fare-limit demonstrations

The CLI includes two illustrative in-memory flights with base fare 100.00, minimum 80.00, and maximum 150.00. A low-season, low-popularity flight with full availability and early booking produces 76.3002 before limits, so its final fare is 80.00. A peak-holiday, high-popularity flight with 1% availability and one day until departure produces 223.925 before limits, so its final fare is 150.00. These are fixed demonstration scenarios, not records imported from the CSV. The maximum of 150.00 is specific to these examples, not a universal percentage rule.

## 7. Validation and Testing

Run the test suite from the project root:

```bash
python -m unittest discover -s tests -v
```

The current suite contains **40 test methods**. All passed in a verification environment using Python 3.13.5 and NumPy 2.3.5. Several methods exercise multiple inputs through subtests, including 441 scenarios comparing individual and vectorized pricing across pricing boundaries.

| Test file | Coverage |
| --- | --- |
| `test_admin.py` | Flight creation, deletion, absolute and relative seat updates, capacity updates, minimum-fare migration, invalid inputs, and initialization/reset behavior. |
| `test_flight_pricing.py` | Model validation, four-factor pricing, seasonal and booking-day boundaries, sold-out and departed-flight rejection, and fare limits. |
| `test_search.py` | Filtering, sold-out visibility, sorting, empty results, and vectorized pricing. |
| `test_cli.py` | The complete demonstration, legacy flag compatibility, readable errors, fare-limit output, and temporary-record cleanup. |

Database tests use disposable databases rather than the normal project database. The suite focuses on backend and CLI behavior; it does not include automated Streamlit interaction tests. Passing these tests does not establish that every interface, dependency version, or input condition has been covered.

## 8. Known Limitations

### Scope and deployment

The data and pricing rules are fictional and predefined, not connected to live airline inventory or inferred from demand. The application does not implement authentication, booking, payment, timezone conversion, or a production concurrency strategy. Its administrator controls are intended for a local demonstration.

### Dates and reproducibility

The Streamlit date range is hard-coded to the supplied dataset, and its searches use the current local time. Future maintenance is needed for a different schedule range. The CLI's `--as-of` option supports reproducible historical demonstrations.

### SQLite and CSV synchronization

SQLite and CSV are not synchronized by one shared transaction. If CSV synchronization fails, the SQLite seat update has already committed. Only remaining seats are mirrored: capacity and other fields can differ between stores. In particular, increasing capacity in SQLite and then saving seats above the CSV's old capacity can make the CSV unsuitable for reinitialization until those fields are aligned. Keep consistent backups before editing inventory or rebuilding the database.

### Fare precision and validation

Fare inputs should use cent precision. Because the implementation applies limits before final rounding, a limit with more than two decimal places can be crossed by rounding. The supplied fare inputs do not have this issue. Lower-level database inserts also bypass some `Flight` and administrative validation, so application-level helpers should be used for normal changes.