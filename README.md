# Potter Airlines Dynamic Revenue Management System

## Purpose

Potter Airlines is a local administrator application for dynamic flight pricing and seat-inventory management. It uses four explainable pricing factors: route popularity, remaining-seat ratio, seasonality, and days until departure. Administrators use a Streamlit interface to search flights, compare fares, and change remaining seats.

The implemented workflow is: **load CSV data into SQLite -> retrieve matching flights -> create validated Flight objects -> price available flights together with NumPy -> sort and display results -> update seats -> reload and reprice**. Sold-out flights remain visible without a fare.

**DEMO Video Link**: https://drive.google.com/file/d/11noPX5H_DQ34iegfPBhKFw1f_tzb8VCh/view?usp=sharing

### Implementation at a Glance

| Requirement | Implementation and evidence |
| --- | --- |
| Core functionality | Data loading, search, batch pricing, ranking, and persistent seat updates; see **Setup/Run Steps** and **Design Choices**. |
| **Update at least one operational value such as seats remaining** | **`seats_remaining` is updated through the administrator interface, saved in SQLite, and used to recalculate the fare.** See **Design Choices: Updating an Operational Value: Seats Remaining**. |
| Pricing logic | Four factors, an 80%-of-base minimum, configured maximum fares, and input-change examples; see **Pricing Logic**. |
| Meaningful class | `Flight` validates flight records and provides departure and seat-ratio properties used by pricing. See **Pricing Logic: Flight Class - Connecting Data, Pricing and Updates**. |
| Functions and vectorization | Focused backend functions and `analyze_fares()` using NumPy; see **Design Choices**. |
| Persistence and data | Explicit `CREATE TABLE`, parameterized INSERT/SELECT/UPDATE/DELETE, and database tests; see **Design Choices: SQLite Schema and Parameterized CRUD**. |
| Robustness and assertions | Empty searches, sold-out flights, fare limits, invalid seat counts, and automated checks; see **Design Choices: Validation, Edge Cases and Tests**. |
| Code organization | Separate interface, model, pricing, search, and persistence modules; shared pricing constants; see **Design Choices**. |

## Setup/Run Steps

### Requirements and Virtual Environment

Use Python 3.10 or later. `requirements.txt` declares `numpy>=1.24,<3` and `streamlit>=1.30,<2`. SQLite and `unittest` are included with Python.

Open a terminal in the project root, where `requirements.txt` is located. Create a virtual environment:

```bash
python -m venv .venv
```

Activate it using the command for your terminal.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt alternative:

```bat
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### Install Dependencies and Start the Application

Install dependencies, create the database, and start the application:

```bash
python -m pip install -r requirements.txt
python database/init_db.py
streamlit run frontend/app.py
```

Open the **Local URL** printed in the terminal in your browser. Keep the terminal running while using the application; press `Ctrl+C` to stop it.

### Initializing the Database

Reset database: `python database/init_db.py --reset` replaces SQLite with the current CSV contents. Seat updates to existing CSV records are also saved to that CSV, so reset does not necessarily restore the original inventory. Back up both files before modifying demonstration data.

### Using the Interface

Select an origin, destination, and date; compare the matching flights by price or departure time. In **Admin: update seats remaining**, select a flight, enter an integer count, and press **Update seats**. The application saves the update, reloads the flight, recalculates its fare, and refreshes the results. The interface edits remaining seats; flight creation, deletion, and capacity changes are backend operations, not interface buttons.

**The operational value being updated is `seats_remaining`. The change is persisted in SQLite, not just displayed temporarily in the interface.**

## Design Choices

### Project Structure and Key Functions

The following are the main files supporting the Streamlit workflow. Function parameters describe inputs; return values describe what callers receive.

| File | Responsibility and main input/output contracts |
| --- | --- |
| `frontend/app.py` | `main()` coordinates the page. `render_search_controls()` returns `(origin, destination, date_string)`. `render_results(results)` displays `(Flight, price)` pairs. `render_seat_admin(results, as_of)` saves seat edits and displays repricing; both rendering functions return no data. `is_sold_out(flight, price)` returns a Boolean; `fare_text(flight, price)` returns a formatted fare or `SOLD OUT`. |
| `backend/flight.py` | `Flight.from_row(row)` accepts an eleven-column database row and returns a validated `Flight`. `departure` returns its departure datetime; `seat_fraction` returns remaining seats divided by capacity. |
| `backend/pricing.py` | `calculate_price(flight, as_of=None)` returns `PriceResult`, containing the flight ID, final fare, and four multipliers. `season_factor_for(departure)` returns a seasonal multiplier. |
| `backend/search.py` | `search_flights(origin, destination, flight_date, as_of=None)` returns price-ranked `(Flight, price)` pairs, and **drops any flight whose departure is before the current time**; sold-out prices are `None`. `get_origins(as_of=None)`, `get_destinations(origin, as_of=None)`, and `get_flight_dates(origin, destination, as_of=None)` return lists of strings. `analyze_fares(flights, as_of=None)` returns a NumPy fare array; see **NumPy Vectorized Calculation** below. |
| `backend/admin.py` | `add_flight(data)` accepts a mapping of the schema fields (`minimum_fare` is optional), calculates/checks the 80% minimum, inserts the flight, and returns a `Flight`. `update_capacity(flight_id, seat_capacity)` returns the saved capacity without changing remaining seats. |
| `database/db.py` | `get_connection()` supplies a managed SQLite connection. Read/write functions and their return values are listed under **SQLite Schema and Parameterized CRUD** below. |
| `database/init_db.py` | `main(reset=False)` imports the CSV using `schema.sql`, checks the imported row count, and creates the database. An existing database requires explicit reset. |
| `database/migrate_minimum_fares.py` | `migrate_minimum_fares()` updates saved minimum fares to 80% of base and returns the number of changed rows. |
| `data/potter_airline_routes_dataset_regenerated.csv` | Supplies 19,006 fictional flights across twelve directional routes between Toronto, Montreal, Ottawa, and Vancouver, dated October 2, 2026 to October 2, 2027. |
| `tests/` | Contains automated model, pricing, database, search, and runnable-workflow checks; see **Validation, Edge Cases and Tests** below. |

`as_of` is an optional reference `datetime`; omission uses the current local time. Search dates use `YYYY-MM-DD`, and departure times use `HH:MM`.

### Flight Class and Separation of Responsibilities

`Flight` is a frozen dataclass, not just a storage container: construction checks integer seats, positive capacity, valid dates, finite fares, and fare ordering. Its computed properties support pricing. Because it is an immutable snapshot, it is reloaded after a database update. The interface calls backend functions instead of duplicating SQL or pricing rules.

The **Flight Class - Connecting Data, Pricing and Updates** subsection at the end of **Pricing Logic** explains the class members and their role in the complete workflow.

### NumPy Vectorized Calculation

**Location:** `backend/search.py`, called by `search_flights()`.

```python
def analyze_fares(flights: list[Flight], as_of: datetime | None = None):
```

**Inputs:** a list of available, not-yet-departed `Flight` objects and an optional reference datetime. **Output:** a NumPy array with one fare per input flight, preserving input order. Empty input returns an empty float array; sold-out or departed flights are rejected. Search separates sold-out flights before calling this function.

After building arrays of seats, capacities, fares, and booking days, the function calculates seat ratios and applies pricing bands across the batch. The following is an excerpt; the arrays and shared constants are defined earlier in the function/module:

```python
seat_fraction = remaining / capacity
seats_factor = np.select(
    [seat_fraction <= upper for upper, _ in SEAT_FACTOR_BANDS],
    [factor for _, factor in SEAT_FACTOR_BANDS],
)
season_factor = np.array([season_factor_for(departure) for departure in departures])
days_until_flight_factor = np.select(
    [days <= upper for upper, _ in DAYS_FACTOR_BANDS],
    [factor for _, factor in DAYS_FACTOR_BANDS], default=VERY_EARLY_FACTOR,
)
raw = base * route_factor
raw *= seats_factor * season_factor * days_until_flight_factor
return np.floor(np.clip(raw, minimum, maximum) * 100 + 0.5 + 1e-9) / 100
```

The meaningful vectorized work is the array division, conditional factor selection, multiplication, fare clipping, and rounding across flights. Python comprehensions still prepare arrays and conditions; the function does not repeatedly call single-flight pricing in a Python loop. Shared constants and `season_factor_for()` keep individual and batch rules aligned.

**Verification:** `SearchTests.test_vectorized_pricing_across_factor_boundaries` in `tests/test_search.py` compares batch and individual prices over 441 scenarios. Separate tests assert expected factor values and fare limits; agreement between implementations alone is not the only check.

### SQLite Schema and Parameterized CRUD

`database/schema.sql` explicitly defines all eleven fields and database constraints:

```sql
CREATE TABLE flights (
    flight_id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    flight_date TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    route_popularity TEXT NOT NULL CHECK (route_popularity IN ('High', 'Medium', 'Low')),
    seat_capacity INTEGER NOT NULL CHECK (seat_capacity > 0),
    seats_remaining INTEGER NOT NULL CHECK (seats_remaining >= 0 AND seats_remaining <= seat_capacity),
    base_fare REAL NOT NULL CHECK (base_fare >= 0),
    minimum_fare REAL NOT NULL CHECK (minimum_fare >= 0 AND minimum_fare <= base_fare),
    maximum_fare REAL NOT NULL CHECK (maximum_fare >= base_fare),
    CHECK (origin <> destination)
);
```

The schema enforces valid ranges and fare ordering; the 80% minimum policy is enforced by the supplied data and administrative creation logic, not by a separate SQL percentage constraint.

| Operation | Functions, inputs, and results |
| --- | --- |
| INSERT | `insert_flight(flight)` accepts a complete field mapping and returns its ID. `add_flight(data)` provides model and minimum-policy validation before insertion. |
| SELECT | `get_flight_by_id(flight_id)` returns one eleven-field row or `None`. `get_flights_by_destination(destination)` returns matching rows containing ID, route, date, time, and seats. |
| UPDATE | `set_seats(flight_id, seats_remaining)` sets an absolute count; `update_seats(flight_id, seat_change)` applies an integer difference. Both return the saved count. `set_capacity(flight_id, seat_capacity)` returns the new capacity and preserves remaining seats. |
| DELETE | `delete_flight(flight_id)` returns `True` when a row is removed and `False` when no row matches. |

All four operations bind values separately from SQL text. For example, `set_seats()` uses:

```python
cursor = connection.execute(
    "UPDATE flights SET seats_remaining = ? "
    "WHERE flight_id = ? AND ? BETWEEN 0 AND seat_capacity",
    (seats_remaining, flight_id, seats_remaining),
)
```

INSERT uses eleven `?` placeholders; SELECT and DELETE bind the flight ID or destination through parameter tuples. Dynamically assembled column lists are fixed by the code, not supplied by users. Connection handling commits successful transactions, rolls back failed ones, and closes connections.

**CRUD evidence:** `tests/test_admin.py` includes `test_add_complete_flight`, `test_set_seats_persists_and_checks_capacity`, `test_update_seats_persists_and_checks_bounds`, and `test_delete_flight`. These insert records, read them back, verify persisted updates, and confirm deleted records are no longer retrievable. Run them using:

```bash
python -m unittest discover -s tests -p "test_admin.py" -v
```

SQLite is the operational store. Default-database seat updates also copy `seats_remaining` to matching CSV rows. Other edits are not fully mirrored; see **Known Limitations**.

### Updating an Operational Value: Seats Remaining

**Required workflow step: "Update at least one operational value such as seats remaining."** The application implements this by changing the saved `seats_remaining` field for a selected flight, then using the saved value to recalculate its fare.

**Location:** `render_seat_admin(results, as_of)` in `frontend/app.py`, supported by `set_seats(flight_id, seats_remaining)` in `database/db.py`.

The administrator selects a flight, enters a new integer count, and clicks **Update seats**. `set_seats()` checks that the flight exists and that the count is between zero and capacity, then commits a parameterized SQL UPDATE. Invalid inputs are rejected rather than replacing the saved count.

After a successful update, the interface reloads the database row as a new `Flight`. It displays `SOLD OUT` for zero seats or calculates a new fare for a positive count. The core call sequence is shown below; interface rendering and error handling are omitted:

```python
set_seats(selected_id, int(new_seats))
updated_flight = Flight.from_row(get_flight_by_id(selected_id))

if updated_flight.seats_remaining == 0:
    updated_text = SOLD_OUT
else:
    updated_text = f"{calculate_price(updated_flight, as_of).price:.2f}"
```

`main()` then calls `search_flights()` again so the results table reflects the saved inventory, current availability, and recalculated fares. A valid update does not necessarily change the price: the count may remain within the same pricing band, or a fare limit may apply.

**Persistence evidence:** `test_set_seats_persists_and_checks_capacity` and `test_update_seats_persists_and_checks_bounds` in `tests/test_admin.py` read records back after updates and check the saved counts. They also verify that out-of-range updates are rejected without changing valid saved data. The **Example: Changing Remaining Seats** under **Pricing Logic** illustrates how crossing a band changes a fare.

### Validation, Edge Cases and Tests

| Case | How to demonstrate it | Expected behavior and implementation |
| --- | --- | --- |
| No flights | Select Montreal to Ottawa on November 17, 2026 in the supplied schedule. The date remains selectable even with no matching records. | The interface displays **No flights available for the selected route and date.** Search returns an empty list; `render_results()` handles it. |
| Sold out / zero seats | Set an available future flight to zero seats, then restore a valid positive count. | The flight stays visible and selectable, displays **SOLD OUT**, and can be updated again. Search uses `None` for its fare instead of a zero-price ticket. |
| Fare above maximum | Run the controlled December holiday scenario in `PricingTests.test_fare_bounds_and_invalid_inputs`. | Raw fare 223.925 is capped at 150.00. The same test checks a discounted fare is raised to its minimum; batch limits are tested separately. |
| Seats outside capacity | For a flight with capacity 180, enter 190 remaining seats and press **Update seats**. | `set_seats()` rejects the update; the interface reports **Could not update seats: Seats must stay between 0 and 180**. The previous valid value remains saved. |

Record original seat counts and restore them after demonstrations. UI searches use the current local time; choose a future flight. Fixed-reference backend tests remain reproducible after the schedule dates pass.

Additional checks reject non-integer seats, invalid capacity, malformed dates, duplicate IDs, and non-finite fares. Initialization asserts that the database row count equals the imported CSV row count. Relevant evidence is in `test_admin.py`, `test_flight_pricing.py`, and `test_search.py`.

Run all supplied tests:

```bash
python -m unittest discover -s tests -v
```

The supplied suite contains **39 test methods**, including database-persistence and vectorization checks. Database tests use temporary databases rather than editing the normal project inventory. The suite does not include automated Streamlit interaction tests.

A demonstration can follow the actual workflow: search and rank flights, change seats and explain the fare, inspect `Flight` and `analyze_fares()`, show the schema and CRUD evidence, and trigger a checked edge case. The recorded demonstration is submitted separately.

## Pricing Logic

### Pricing Formula

```text
Raw fare = base_fare * route_factor * seats_factor
           * season_factor * days_until_flight_factor
```

### Factors and Ranges

| Factor | Implemented rules |
| --- | --- |
| Route popularity | Low: **0.97**; Medium: **1.00**; High: **1.06**. |
| Remaining-seat ratio `r` | `0 < r <= 0.05`: **1.30**; `0.05 < r <= 0.10`: **1.22**; `0.10 < r <= 0.20`: **1.15**; `0.20 < r <= 0.40`: **1.05**; `0.40 < r <= 0.65`: **0.97**; `0.65 < r <= 1`: **0.92**. Zero means sold out. |
| Seasonality | Low: **0.90**; Regular: **1.00**; Peak: **1.12**; Peak Holiday: **1.25**. |
| Calendar days until departure | 0-3: **1.30**; 4-14: **1.15**; 15-30: **1.05**; 31-60: **1.00**; 61+: **0.95**. |

Season dates are inclusive: Low is January 6-March 31 and November 1-December 19; Regular is April 1-June 24 and September 1-October 31; Peak is June 25-August 31; Peak Holiday is December 20-January 5. The actual seat ratio is used without rounding it to a whole percentage. Departure time determines whether a flight has departed but adds no separate multiplier.

### Minimum and Maximum Fares

The supplied data and `add_flight()` use **minimum_fare = 0.80 * base_fare**, rounded to cents. Maximum fares are stored per flight, not calculated from one universal percentage. The following excerpt from `calculate_price()` applies both limits and rounds the result:

```python
raw = flight.base_fare * route_factor
raw *= seats_factor * season_factor * days_until_flight_factor
bounded = min(flight.maximum_fare, max(flight.minimum_fare, raw))
price = floor(bounded * 100 + 0.5 + 1e-9) / 100
```

### Example: Changing Remaining Seats

For a base fare of 100.00, Medium popularity, regular season, and 19 days until departure, changing remaining seats from 60/100 to 20/100 changes the seat factor from 0.97 to 1.15. With limits of 80.00 and 250.00, the fare rises from **101.85 to 120.75**. Changes within the same band may leave the fare unchanged.

### Example: Enforcing the Maximum Fare

The existing pricing test uses a High-popularity flight departing December 20, 2026, with 1/100 seats remaining and a reference date of December 19. A base fare of 100.00 produces `100 * 1.06 * 1.30 * 1.25 * 1.30 = 223.925`. With a configured maximum of 150.00, the returned fare is **150.00**. This controlled test is independent of the current date; changing seats in today's interface does not guarantee the same factors or cap activation.

### Flight Class - Connecting Data, Pricing and Updates

**Location:** `backend/flight.py`. `Flight` represents one scheduled flight and is implemented with `@dataclass(frozen=True)`. It provides named, validated attributes that the search, pricing, and interface functions use consistently instead of repeatedly interpreting raw database rows.

Its eleven fields contain the flight ID, origin and destination, departure date and time, route popularity, capacity, remaining seats, and the three fare inputs: base, minimum, and maximum fare.

| Class member | Input or behavior | Role in the application |
| --- | --- | --- |
| `Flight.from_row(row)` | Accepts a database row in the expected eleven-column order and returns a `Flight`; rejects a missing row or incorrect column count. | Converts retrieved or updated SQLite records into the same model used by pricing and display. |
| `__post_init__()` | Automatically validates fields after construction, including required identifiers, different cities, canonical date/time formats, integer seats, positive capacity, finite fares, and valid seat/fare ranges. | Rejects invalid flight data before it is used by application calculations. |
| `departure` | Combines `flight_date` and `departure_time` into a `datetime`. | Supports departure filtering and the seasonality and days-until-departure calculations. |
| `seat_fraction` | Returns `seats_remaining / seat_capacity`. | Supplies the remaining-seat ratio used to select the single-flight seat multiplier. |

This is a meaningful class because it combines flight data with validation and derived properties needed by the application. Final fare calculation remains in `pricing.py`, while SQL operations remain in `database/db.py`; the class does not duplicate those responsibilities.

**Connection to operational updates:** because a `Flight` is frozen, the interface does not assign a new value directly to an existing object's `seats_remaining`. It saves the change in SQLite and constructs a new `Flight` from the updated record. Repricing therefore uses the newly saved inventory rather than an outdated object. A zero-seat `Flight` remains a valid record representing a sold-out flight; search displays it without a fare, and an administrator can restore its availability.

**Class verification:** `tests/test_flight_pricing.py` includes `test_database_row_and_computed_properties`, `test_invalid_flight_fields`, `test_seat_counts_require_integers`, and `test_fares_require_finite_numbers` to check row conversion, derived properties, and invalid inputs.

## Known Limitations

The application uses fictional data and predefined factors, not live demand. It is a local administrator demonstration without authentication or a booking/payment system. Datetimes have no timezone information, and the interface's selectable date range is fixed to the supplied schedule.

SQLite updates and CSV synchronization are not one shared transaction. Only remaining seats are mirrored; capacity changes and other edits may leave the stores inconsistent. A CSV write failure can occur after SQLite has committed. Back up and align both stores before reinitialization.

Use cent-precision fare inputs: clipping happens before rounding, so bounds with additional decimal places may be crossed by the rounding step. Lower-level database writes also bypass some model-level validation; use the application helpers for normal operations.
