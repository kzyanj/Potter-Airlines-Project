# Potter Airlines Dynamic Revenue Management System

A Python project for calculating explainable flight prices from time to departure,
route demand, remaining seats, and seasonality. This repository currently contains
the flight dataset and SQLite foundation. The pricing model and runnable user
workflow are still in progress.

## Project structure

```text
data/       Source flight CSV
database/   SQLite schema, data import, and database operations (Backend)
backend/    Flight class, pricing, filtering, and ranking (to be built)
frontend/   Streamlit interface (to be built)
tests/      Database and application tests (to be built)
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

This creates `database/potter_airlines.db`, which is ignored by Git. **Running
this command again replaces the database and erases flight edits and seat changes.**
The database layer uses Python's standard library. The planned vectorized
analysis will require Pandas or NumPy once implemented.

There is no complete pricing or command-line workflow to run yet.

## Project task tracker

### Backend

- [x] Add the supplied flight dataset and SQLite schema.
- [x] Import flights and provide parameterized database operations.
- [x] Validate flight IDs and seat limits during import or updates.

- [ ] Add a meaningful `Flight` class and pricing functions.
- [ ] Define explainable factors for time to departure, route demand, seat
      availability, and seasonality; keep prices within sensible minimum and
      maximum bounds.
- [ ] Calculate prices for multiple flights and filter or rank useful results.
- [ ] Use Pandas or NumPy vectorized operations for at least one meaningful
      calculation or analysis across multiple flights.
- [ ] Add assertions and handle pricing edge cases.

### Frontend

- [ ] Build a Streamlit interface.
- [ ] Add origin, destination, and departure date selection.
- [ ] Show flights and calculated prices; allow flight selection.
- [ ] Provide a control to update and display remaining seats.

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
