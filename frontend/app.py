"""Potter Airlines Dynamic Revenue Management System - Streamlit admin UI.

This is an ADMIN / REVENUE MANAGEMENT tool, not a customer booking app:
it searches flights, shows their backend-calculated fares, and lets an
administrator adjust seats_remaining to see how that changes the fare.

All pricing and database logic lives in backend/ and database/db.py.
This file only calls those functions and renders the results - it does
not calculate fares or run its own SQL.

Run with:  streamlit run frontend/app.py
"""

import sys
from datetime import date, datetime
from pathlib import Path

import streamlit as st

# Streamlit only puts this file's own folder on sys.path, but backend/ and
# database/ are imported as top-level packages, so add the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.flight import Flight
from backend.pricing import calculate_price
from backend.search import get_destinations, get_origins, search_flights
from database.db import get_flight_by_id, set_seats

st.set_page_config(page_title="Potter Airlines Revenue Management", layout="wide")
st.title("Potter Airlines Dynamic Revenue Management System")
st.caption("Search flights, review calculated fares, and adjust seat inventory.")

MIN_SEARCH_DATE = date(2026, 10, 2)
MAX_SEARCH_DATE = date(2027, 10, 2)
SOLD_OUT = "SOLD OUT"


def is_sold_out(flight, price):
    """A flight is sold out when it has no seats or the backend gave no price."""
    return flight.seats_remaining == 0 or price is None


def fare_text(flight, price):
    return SOLD_OUT if is_sold_out(flight, price) else f"{price:.2f}"


def render_search_controls():
    """Origin / destination / date pickers, populated from backend.search.

    Each dependent dropdown's key includes its parent selections, so
    Streamlit always shows a fresh, valid set of choices when an earlier
    choice changes.
    """
    st.header("Flight search")

    origins = get_origins()
    if not origins:
        st.warning("No upcoming flights were found in the database.")
        return None, None, None
    origin = st.selectbox("Origin", origins, key="origin_select")

    destinations = get_destinations(origin)
    if not destinations:
        st.warning(f"No destinations currently available from {origin}.")
        return origin, None, None
    destination = st.selectbox("Destination", destinations, key=f"destination_select_{origin}")

    selected_date = st.date_input(
        "Departure date",
        value=MIN_SEARCH_DATE,
        min_value=MIN_SEARCH_DATE,
        max_value=MAX_SEARCH_DATE,
        key="date_input",
    )
    # search_flights() expects a YYYY-MM-DD string.
    return origin, destination, selected_date.isoformat()


def render_results(results):
    """Show the matching flights and their backend-calculated fares,
    sortable by price or by departure time.
    """
    st.header("Matching flights")

    if not results:
        st.info("No flights available for the selected route and date.")
        return

    sort_choice = st.radio("Sort by", ["Price", "Departure time"], horizontal=True)
    if sort_choice == "Price":
        # Sold-out flights (price None) sort last.
        sorted_results = sorted(
            results, key=lambda item: (is_sold_out(*item), item[1] or 0)
        )
    else:
        sorted_results = sorted(results, key=lambda item: item[0].departure)

    table_rows = [
        {
            "Flight ID": flight.flight_id,
            "Origin": flight.origin,
            "Destination": flight.destination,
            "Date": flight.flight_date,
            "Time": flight.departure_time,
            "Seats remaining": flight.seats_remaining,
            "Capacity": flight.seat_capacity,
            "Fare": fare_text(flight, price),
            "Status": SOLD_OUT if is_sold_out(flight, price) else "Available",
        }
        for flight, price in sorted_results
    ]
    st.dataframe(table_rows, width="stretch", hide_index=True)


def render_seat_admin(results, as_of):
    """Let an administrator set an exact seats_remaining value for one
    flight from the search results, then show the recalculated fare.

    Seat validation (0 <= seats_remaining <= capacity) is enforced by
    database.db.set_seats(), not by this function.
    """
    st.header("Admin: update seats remaining")

    flight_lookup = {flight.flight_id: (flight, price) for flight, price in results}
    # Sorted by flight_id (not price) so the option order - and therefore
    # the selection - stays stable even after an update changes a fare.
    flight_ids = sorted(flight_lookup.keys())
    selected_id = st.selectbox("Flight to update", flight_ids, key="admin_flight_select")
    selected_flight, current_price = flight_lookup[selected_id]

    st.write(
        f"Current seats remaining: {selected_flight.seats_remaining} of "
        f"{selected_flight.seat_capacity} — current fare: "
        f"{fare_text(selected_flight, current_price)}"
    )

    # No max_value here on purpose: set_seats() is the real gatekeeper for
    # capacity, so an out-of-range entry can actually reach it and be
    # rejected with a ValueError instead of being silently clamped here.
    new_seats = st.number_input(
        "New seats remaining",
        min_value=0,
        value=selected_flight.seats_remaining,
        step=1,
        key=f"new_seats_input_{selected_id}",
    )

    if st.button("Update seats"):
        try:
            set_seats(selected_id, int(new_seats))
        except ValueError as error:
            st.error(f"Could not update seats: {error}")
        else:
            st.success(f"Seats remaining for {selected_id} updated to {int(new_seats)}.")

            updated_flight = Flight.from_row(get_flight_by_id(selected_id))
            if updated_flight.seats_remaining == 0:
                updated_text = SOLD_OUT
            else:
                updated_text = f"{calculate_price(updated_flight, as_of).price:.2f}"

            st.write(
                f"Recalculated fare for {selected_id}: "
                f"{fare_text(selected_flight, current_price)} → {updated_text} "
                f"(seats {selected_flight.seats_remaining} → {updated_flight.seats_remaining})"
            )


def main():
    as_of = datetime.now()

    origin, destination, flight_date = render_search_controls()
    if not (origin and destination and flight_date):
        return

    # Reserve the results table's position now, but fill it in last (below)
    # so it can reflect any seat change made in the admin section.
    results_slot = st.container()
    st.divider()
    admin_slot = st.container()

    results = search_flights(origin, destination, flight_date, as_of)

    with admin_slot:
        if results:
            render_seat_admin(results, as_of)
        else:
            st.info("Admin controls appear once a search returns flights.")

    # Re-query after any update above, so the table below reflects it.
    results = search_flights(origin, destination, flight_date, as_of)
    with results_slot:
        render_results(results)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        st.error(str(error))
