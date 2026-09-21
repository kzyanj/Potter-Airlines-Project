# Potter Airlines Dynamic Revenue Management System

A Python project for calculating explainable flight prices from time to departure,
route demand, remaining seats, and seasonality. The flight dataset, SQLite database,
pricing/search backend, and Streamlit admin interface are implemented; testing and
final documentation are still in progress.

## Project structure

```text
data/       Source flight CSV
database/   SQLite schema, data import, and database operations (Backend)
backend/    Flight class, pricing, search, and admin operations (Backend)
frontend/   Streamlit admin/revenue-management interface (Frontend)
tests/      Database and application tests
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

From the project root, run:

```bash
python database/init_db.py
```

This creates `database/potter_airlines.db`, which is ignored by Git. If the
database already exists, this command stops without changing it. **Only run
`python database/init_db.py --reset` when you intentionally want to rebuild
the database from the CSV; resetting erases saved flight edits and seat changes.**

The database layer uses Python's standard library. `backend/search.py` uses
NumPy for a vectorized fare calculation across multiple flights.

Search, price, and inspect flights from the command line:

```bash
python -m backend.cli --origin Toronto --destination Montreal --date 2026-10-02
```

Or launch the Streamlit admin interface:

```bash
streamlit run frontend/app.py
```

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

- [x] Build a Streamlit interface.
- [x] Add origin, destination, and departure date selection.
- [x] Show multiple flights and calculated prices.
- [x] Allow filtering/ranking by useful criteria such as price and departure time.
- [x] Provide a control to update and display remaining seats.
- [x] Demonstrate how changing an operational input such as seats_remaining can
      change the calculated fare.

### Testing

- [ ] Test database SELECT, INSERT, UPDATE, and DELETE operations.
- [ ] Test pricing boundaries and minimum/maximum fare rules.
- [ ] Test invalid seat counts and capacity limits.
- [ ] Test flight filtering, ranking, and seat updates through the interface.
- [ ] Demonstrate at least one checked edge case.

### Deliverables

- [ ] Document the final pricing logic, setup, run steps, design choices, and
      known limitations here.
- [ ] Provide a runnable interaction or script workflow.
- [ ] Record a 4–5 minute demo showing the program, a pricing decision,
      meaningful code, and a checked edge case.

The project specification accepts a command-line or script workflow; Streamlit
is the team's planned frontend, not a specification requirement. LLM/API use
and advanced optimization are optional. A connecting-flight search is not required.
