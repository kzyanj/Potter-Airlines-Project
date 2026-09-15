"""
Potter Airlines - fictional flight dataset generator.

Generates data/aircraft_types.csv, data/routes.csv and data/flights.csv
containing raw, fictional flight data only. No fares, demand scores,
seasons, or other values that belong to the pricing model are generated
here - those are derived later in Python from this raw data.

All aircraft names, seat capacities and scheduled durations are FICTIONAL
Potter Airlines project assumptions, not claims about real airlines.

Run with:  python data/generate_data.py
"""

import csv
import os
import random
from datetime import datetime, timedelta

# Reproducible dataset every time the script is run.
random.seed(8431)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AIRCRAFT_CSV_PATH = os.path.join(SCRIPT_DIR, "aircraft_types.csv")
ROUTES_CSV_PATH = os.path.join(SCRIPT_DIR, "routes.csv")
FLIGHTS_CSV_PATH = os.path.join(SCRIPT_DIR, "flights.csv")

# --------------------------------------------------------------------
# Fixed reference data
# --------------------------------------------------------------------

# (aircraft_type_id, aircraft_name, capacity)
# A small fictional Potter Airlines fleet. Real aircraft model names are
# used for flavour, but these seat counts are project assumptions only.
AIRCRAFT_TYPES = [
    ("A001", "E195-E2", 132),
    ("A002", "Dash 8-400", 78),
    ("A003", "A220-300", 145),
]

# City names shown to travellers for each airport code.
CITY_BY_AIRPORT = {
    "YYZ": "Toronto",
    "JFK": "New York",
    "YVR": "Vancouver",
    "YUL": "Montreal",
    "BOS": "Boston",
    "ORD": "Chicago",
    "EWR": "Newark",
    "YOW": "Ottawa",
}

# (route_id, origin, destination, route_popularity, scheduled_duration_minutes)
# The first 7 routes are the original YYZ-hub network. The rest are a small
# set of connecting/return routes added only so direct AND one-stop
# itineraries (e.g. YYZ -> YUL -> BOS) become possible. This is deliberately
# NOT a full airline network - just enough to demonstrate connections.
ROUTES = [
    ("R001", "YYZ", "JFK", "High", 90),
    ("R002", "YYZ", "YVR", "High", 300),
    ("R003", "YYZ", "YUL", "High", 70),
    ("R004", "YYZ", "BOS", "Medium", 85),
    ("R005", "YYZ", "ORD", "Medium", 105),
    ("R006", "YYZ", "EWR", "Low", 95),
    ("R007", "YYZ", "YOW", "High", 60),
    ("R008", "YUL", "BOS", "Medium", 75),
    ("R009", "YUL", "JFK", "Medium", 80),
    ("R010", "YOW", "BOS", "Low", 80),
    ("R011", "YOW", "YUL", "Medium", 55),
    ("R012", "YUL", "YYZ", "High", 70),
    ("R013", "YOW", "YYZ", "High", 60),
    ("R014", "YVR", "YYZ", "High", 300),
]

# Recurring realistic-looking departure times. Every route is assigned a
# subset of these (sized by popularity) instead of a fully random minute.
SCHEDULE_TIMES = [
    "05:30", "06:30", "07:15", "08:45", "10:30", "12:15", "14:00",
    "15:45", "17:30", "18:45", "20:15", "21:30", "23:15",
]

# How many schedule slots each popularity tier is assigned, and how many
# flights (across the whole generated period) each route in that tier gets.
# Higher popularity -> more slots -> visibly higher average flight frequency.
SLOT_COUNT_BY_POPULARITY = {"High": 9, "Medium": 6, "Low": 3}
FLIGHT_COUNT_RANGE_BY_POPULARITY = {"High": (32, 42), "Medium": (18, 26), "Low": (10, 15)}

# Clock ranges for each time-of-day slot. "Overnight" wraps past midnight
# (9:00 PM-11:59 PM or 12:00 AM-5:59 AM) so it is handled as a fallback.
TIME_SLOTS = {
    "Morning": ((6, 0), (11, 59)),
    "Afternoon": ((12, 0), (16, 59)),
    "Evening": ((17, 0), (20, 59)),
}
TIME_SLOT_NAMES = ["Morning", "Afternoon", "Evening", "Overnight"]

# (low_fraction, high_fraction, label) - fraction of aircraft capacity remaining.
SEAT_BUCKETS = [
    (0.66, 1.00, "66-100%"),
    (0.41, 0.65, "41-65%"),
    (0.21, 0.40, "21-40%"),
    (0.11, 0.20, "11-20%"),
    (0.06, 0.10, "6-10%"),
    (0.00, 0.05, "0-5%"),
]

# Date windows spanning the project's seasonal categories, so representative
# flights exist in every season without simulating a full calendar year.
SEASON_WINDOWS = [
    ("2026-09-16", "2026-10-31"),  # Regular Season
    ("2026-11-01", "2026-12-19"),  # Low Season
    ("2026-12-20", "2027-01-05"),  # Peak Holiday
    ("2027-01-06", "2027-03-31"),  # Low Season
    ("2027-04-01", "2027-06-24"),  # Regular Season
    ("2027-06-25", "2027-08-31"),  # Peak Season
    ("2027-09-01", "2027-10-31"),  # Regular Season
]

SEASON_NAMES = ["Low Season", "Regular Season", "Peak Season", "Peak Holiday"]

MIN_TOTAL_FLIGHTS = 350
MAX_TOTAL_FLIGHTS = 500

# Fictional Potter Airlines connection rule, used only to validate the
# synthetic schedule - never stored on a flight itself.
MIN_LAYOVER_MINUTES = 60
MAX_LAYOVER_MINUTES = 240


# --------------------------------------------------------------------
# Reference table generation
# --------------------------------------------------------------------

def create_aircraft_types():
    """Return the fictional Potter Airlines fleet as a list of dictionaries."""
    aircraft_types = []
    for aircraft_type_id, aircraft_name, capacity in AIRCRAFT_TYPES:
        aircraft_types.append({
            "aircraft_type_id": aircraft_type_id,
            "aircraft_name": aircraft_name,
            "capacity": capacity,
        })
    return aircraft_types


def get_aircraft_capacity(aircraft_type_id, aircraft_types_by_id):
    """Look up an aircraft's seat capacity from aircraft_types.csv data."""
    return aircraft_types_by_id[aircraft_type_id]["capacity"]


def create_routes():
    """Return the fixed list of Potter Airlines routes as dictionaries."""
    routes = []
    for route_id, origin, destination, popularity, duration in ROUTES:
        routes.append({
            "route_id": route_id,
            "origin": origin,
            "destination": destination,
            "origin_city": CITY_BY_AIRPORT[origin],
            "destination_city": CITY_BY_AIRPORT[destination],
            "route_popularity": popularity,
            "scheduled_duration_minutes": duration,
        })
    return routes


# --------------------------------------------------------------------
# Small helpers used both to build flights and to classify them later
# --------------------------------------------------------------------

def _random_date_in_window(window):
    """Pick a random calendar date between the two YYYY-MM-DD strings."""
    start = datetime.strptime(window[0], "%Y-%m-%d")
    end = datetime.strptime(window[1], "%Y-%m-%d")
    span_days = (end - start).days
    offset = random.randint(0, span_days)
    return start + timedelta(days=offset)


def _nudge_to_day_type(date, day_type):
    """Move a date forward a few days until it matches weekday/weekend."""
    while True:
        is_weekend = date.weekday() >= 5  # Saturday=5, Sunday=6
        if (day_type == "weekend") == is_weekend:
            return date
        date += timedelta(days=1)


def _parse_slot(slot_text):
    """Turn a 'HH:MM' schedule slot into (hour, minute) integers."""
    hour_text, minute_text = slot_text.split(":")
    return int(hour_text), int(minute_text)


def classify_time_of_day(departure_datetime_str):
    """Used only for validation/summary - not stored as a dataset column."""
    dt = datetime.strptime(departure_datetime_str, "%Y-%m-%d %H:%M:%S")
    minutes = dt.hour * 60 + dt.minute
    if 6 * 60 <= minutes <= 11 * 60 + 59:
        return "Morning"
    if 12 * 60 <= minutes <= 16 * 60 + 59:
        return "Afternoon"
    if 17 * 60 <= minutes <= 20 * 60 + 59:
        return "Evening"
    return "Overnight"


def classify_day_type(departure_datetime_str):
    """Used only for validation/summary - not stored as a dataset column."""
    dt = datetime.strptime(departure_datetime_str, "%Y-%m-%d %H:%M:%S")
    return "weekend" if dt.weekday() >= 5 else "weekday"


def classify_season(departure_datetime_str):
    """Used only for validation/summary - not stored as a dataset column.
    Season is defined by month/day only, so it repeats every year.
    """
    dt = datetime.strptime(departure_datetime_str, "%Y-%m-%d %H:%M:%S")
    month_day = (dt.month, dt.day)
    if month_day >= (12, 20) or month_day <= (1, 5):
        return "Peak Holiday"
    if (1, 6) <= month_day <= (3, 31):
        return "Low Season"
    if (4, 1) <= month_day <= (6, 24):
        return "Regular Season"
    if (6, 25) <= month_day <= (8, 31):
        return "Peak Season"
    if (9, 1) <= month_day <= (10, 31):
        return "Regular Season"
    return "Low Season"  # (11, 1) - (12, 19)


def classify_seat_bucket(seats_remaining, capacity):
    """Used only for validation/summary - not stored as a dataset column."""
    pct = seats_remaining / capacity
    for low, _high, label in SEAT_BUCKETS:
        if pct >= low:
            return label
    return SEAT_BUCKETS[-1][2]


# --------------------------------------------------------------------
# Schedule + aircraft assignment
# --------------------------------------------------------------------

def assign_schedule_slots(routes):
    """Give every route its own subset of SCHEDULE_TIMES, sized by
    popularity so high-popularity routes fly more often per day.
    """
    slots_by_route = {}
    for route in routes:
        slot_count = SLOT_COUNT_BY_POPULARITY[route["route_popularity"]]
        slots_by_route[route["route_id"]] = random.sample(SCHEDULE_TIMES, slot_count)
    return slots_by_route


def choose_aircraft_for_route(route):
    """Pick an aircraft type with a plausible (but not rigid) bias:
    shorter regional hops lean toward the smaller Dash 8-400, long-haul
    and high-popularity routes lean toward the larger A220-300.
    """
    weights = {"A001": 1.0, "A002": 1.0, "A003": 1.0}

    if route["scheduled_duration_minutes"] <= 75:
        weights["A002"] += 1.5  # short regional hop -> smaller aircraft
    if route["scheduled_duration_minutes"] >= 250:
        weights["A003"] += 2.0  # long haul (e.g. Vancouver) -> bigger aircraft
    if route["route_popularity"] == "High":
        weights["A003"] += 1.0
        weights["A001"] += 0.5
    if route["route_popularity"] == "Low":
        weights["A002"] += 1.0

    aircraft_ids = list(weights.keys())
    return random.choices(aircraft_ids, weights=list(weights.values()))[0]


# --------------------------------------------------------------------
# Flight generation
# --------------------------------------------------------------------

def _make_flight(flight_number, route, aircraft_types_by_id, departure, seat_fraction_range):
    """Build one flight dictionary, deriving arrival time and seats from
    the route's scheduled duration and the aircraft's capacity.
    """
    aircraft_type_id = choose_aircraft_for_route(route)
    capacity = get_aircraft_capacity(aircraft_type_id, aircraft_types_by_id)

    arrival = departure + timedelta(minutes=route["scheduled_duration_minutes"])

    low_pct, high_pct = seat_fraction_range
    seats_remaining = int(round(capacity * random.uniform(low_pct, high_pct)))
    seats_remaining = max(0, min(seats_remaining, capacity))

    return {
        "flight_id": f"PA{1001 + flight_number}",
        "route_id": route["route_id"],
        "aircraft_type_id": aircraft_type_id,
        "departure_datetime": departure.strftime("%Y-%m-%d %H:%M:%S"),
        "arrival_datetime": arrival.strftime("%Y-%m-%d %H:%M:%S"),
        "seats_remaining": seats_remaining,
    }


def generate_flights(routes, aircraft_types_by_id):
    """Build a varied list of fictional flights.

    Frequency per route is driven by popularity (more schedule slots and
    more flights for High routes than Medium, and Medium than Low), while
    season, day-type and seat-occupancy bucket are cycled globally across
    all flights so every category is represented somewhere in the dataset.
    """
    slots_by_route = assign_schedule_slots(routes)
    day_types = ["weekday", "weekend"]

    flights = []
    flight_number = 0
    global_counter = 0  # advances once per flight, across all routes

    for route in routes:
        low, high = FLIGHT_COUNT_RANGE_BY_POPULARITY[route["route_popularity"]]
        num_flights = random.randint(low, high)
        route_slots = slots_by_route[route["route_id"]]

        for i in range(num_flights):
            window = SEASON_WINDOWS[global_counter % len(SEASON_WINDOWS)]
            day_type = day_types[global_counter % 2]
            seat_bucket = SEAT_BUCKETS[global_counter % len(SEAT_BUCKETS)]
            slot = route_slots[i % len(route_slots)]

            date = _random_date_in_window(window)
            date = _nudge_to_day_type(date, day_type)
            hour, minute = _parse_slot(slot)
            departure = date.replace(hour=hour, minute=minute, second=0)

            flight = _make_flight(
                flight_number, route, aircraft_types_by_id, departure, seat_bucket[:2]
            )
            flights.append(flight)

            flight_number += 1
            global_counter += 1

    flights.extend(
        _generate_designed_connections(routes, aircraft_types_by_id, flight_number)
    )
    return flights


def _generate_designed_connections(routes, aircraft_types_by_id, flight_number):
    """Add a small number of hand-designed flight pairs on fixed dates so the
    dataset is guaranteed (not just left to chance) to contain:
      - several valid one-stop connections (60-240 minute layover)
      - at least one candidate connection that is too short (<60 minutes)
      - at least one candidate connection that is too long (>240 minutes)

    These are on top of, and much smaller than, the main random schedule.
    """
    routes_by_id = {r["route_id"]: r for r in routes}

    def leg(route_id, date_text, time_text):
        nonlocal flight_number
        route = routes_by_id[route_id]
        hour, minute = _parse_slot(time_text)
        departure = datetime.strptime(date_text, "%Y-%m-%d").replace(hour=hour, minute=minute)
        flight = _make_flight(flight_number, route, aircraft_types_by_id, departure, (0.4, 0.7))
        flight_number += 1
        return flight

    designed = []

    # Five valid one-stop itineraries (layover between 60 and 240 minutes).
    designed.append(leg("R003", "2027-05-12", "08:00"))  # YYZ -> YUL, arr 09:10
    designed.append(leg("R008", "2027-05-12", "10:25"))  # YUL -> BOS, layover 75 min

    designed.append(leg("R003", "2027-05-12", "14:00"))  # YYZ -> YUL, arr 15:10
    designed.append(leg("R009", "2027-05-12", "16:40"))  # YUL -> JFK, layover 90 min

    designed.append(leg("R007", "2027-05-15", "07:00"))  # YYZ -> YOW, arr 08:00
    designed.append(leg("R010", "2027-05-15", "10:00"))  # YOW -> BOS, layover 120 min

    designed.append(leg("R007", "2027-05-15", "12:00"))  # YYZ -> YOW, arr 13:00
    designed.append(leg("R011", "2027-05-15", "14:05"))  # YOW -> YUL, layover 65 min

    designed.append(leg("R012", "2027-05-19", "06:00"))  # YUL -> YYZ, arr 07:10
    designed.append(leg("R005", "2027-05-19", "09:00"))  # YYZ -> ORD, layover 110 min

    # One candidate connection that is deliberately too short (<60 minutes).
    designed.append(leg("R003", "2027-05-20", "16:00"))  # YYZ -> YUL, arr 17:10
    designed.append(leg("R008", "2027-05-20", "17:35"))  # YUL -> BOS, layover 25 min

    # One candidate connection that is deliberately too long (>240 minutes).
    designed.append(leg("R007", "2027-05-21", "06:00"))  # YYZ -> YOW, arr 07:00
    designed.append(leg("R011", "2027-05-21", "13:00"))  # YOW -> YUL, layover 360 min

    return designed


# --------------------------------------------------------------------
# Connection validation helper (dataset-generation-time only)
# --------------------------------------------------------------------

def find_connection_candidates(flight_a, flight_b, routes_by_id):
    """Beginner-friendly helper for checking whether two raw flights could
    form a one-stop connection. This is ONLY used to validate/describe the
    synthetic dataset - the result is never written back into flights.csv.

    Returns None if the flights cannot connect at all, otherwise a
    dictionary describing the candidate connection and classifying it as
    "Too Short", "Valid", or "Too Long".
    """
    if flight_a["flight_id"] == flight_b["flight_id"]:
        return None  # a flight can never connect to itself

    route_a = routes_by_id[flight_a["route_id"]]
    route_b = routes_by_id[flight_b["route_id"]]

    if route_a["destination"] != route_b["origin"]:
        return None  # the two legs don't join up at the same airport

    arrival = datetime.strptime(flight_a["arrival_datetime"], "%Y-%m-%d %H:%M:%S")
    departure = datetime.strptime(flight_b["departure_datetime"], "%Y-%m-%d %H:%M:%S")
    layover_minutes = (departure - arrival).total_seconds() / 60

    if layover_minutes <= 0:
        return None  # second flight does not actually depart after the first arrives

    if layover_minutes < MIN_LAYOVER_MINUTES:
        classification = "Too Short"
    elif layover_minutes <= MAX_LAYOVER_MINUTES:
        classification = "Valid"
    else:
        classification = "Too Long"

    return {
        "first_flight_id": flight_a["flight_id"],
        "second_flight_id": flight_b["flight_id"],
        "origin": route_a["origin"],
        "via_airport": route_a["destination"],
        "destination": route_b["destination"],
        "arrival_at_via": flight_a["arrival_datetime"],
        "next_departure": flight_b["departure_datetime"],
        "layover_minutes": layover_minutes,
        "classification": classification,
    }


def scan_for_connection_candidates(routes, flights):
    """Find every candidate one-stop connection in the generated schedule.

    Only compares flights on routes that could actually join up (route A's
    destination equals route B's origin) and that depart the same calendar
    day the first flight lands, which keeps this fast and meaningful.
    """
    routes_by_id = {r["route_id"]: r for r in routes}

    flights_by_route = {}
    for flight in flights:
        flights_by_route.setdefault(flight["route_id"], []).append(flight)

    candidates = []
    for route_a in routes:
        for route_b in routes:
            if route_a["route_id"] == route_b["route_id"]:
                continue
            if route_a["destination"] != route_b["origin"]:
                continue

            for flight_a in flights_by_route.get(route_a["route_id"], []):
                arrival_date = flight_a["arrival_datetime"][:10]
                for flight_b in flights_by_route.get(route_b["route_id"], []):
                    if flight_b["departure_datetime"][:10] != arrival_date:
                        continue
                    candidate = find_connection_candidates(flight_a, flight_b, routes_by_id)
                    if candidate is not None:
                        candidates.append(candidate)

    return candidates


# --------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------

def validate_aircraft(aircraft_types, flights):
    """Checks 1-3: aircraft reference data is sound and fully used."""
    aircraft_ids = [a["aircraft_type_id"] for a in aircraft_types]
    assert len(aircraft_ids) == len(set(aircraft_ids)), "Duplicate aircraft_type_id found"

    for aircraft in aircraft_types:
        assert aircraft["capacity"] > 0, f"Non-positive capacity for {aircraft['aircraft_type_id']}"

    aircraft_id_set = set(aircraft_ids)
    for flight in flights:
        assert flight["aircraft_type_id"] in aircraft_id_set, (
            f"Flight {flight['flight_id']} references unknown aircraft_type_id "
            f"{flight['aircraft_type_id']}"
        )


def validate_routes(routes):
    """Checks 4-6: route reference data is sound."""
    route_ids = [r["route_id"] for r in routes]
    assert len(route_ids) == len(set(route_ids)), "Duplicate route_id found"

    for route in routes:
        assert route["origin"] != route["destination"], (
            f"Route {route['route_id']} has identical origin and destination"
        )
        assert route["scheduled_duration_minutes"] > 0, (
            f"Route {route['route_id']} has a non-positive scheduled duration"
        )


def validate_flights(routes, aircraft_types_by_id, flights):
    """Checks 7-19: the generated flights are internally consistent and
    cover every scenario the project needs (popularity, time-of-day,
    weekday/weekend, season, seat availability).
    """
    routes_by_id = {r["route_id"]: r for r in routes}

    # 7. Approximately 350-500 total flights.
    assert MIN_TOTAL_FLIGHTS <= len(flights) <= MAX_TOTAL_FLIGHTS, (
        f"Expected {MIN_TOTAL_FLIGHTS}-{MAX_TOTAL_FLIGHTS} flights, found {len(flights)}"
    )

    # 8. Unique flight ids.
    flight_ids = [f["flight_id"] for f in flights]
    assert len(flight_ids) == len(set(flight_ids)), "Duplicate flight_id found"

    for flight in flights:
        # 9. Every flight route_id exists.
        assert flight["route_id"] in routes_by_id, (
            f"Flight {flight['flight_id']} references unknown route_id {flight['route_id']}"
        )
        route = routes_by_id[flight["route_id"]]

        departure = datetime.strptime(flight["departure_datetime"], "%Y-%m-%d %H:%M:%S")
        arrival = datetime.strptime(flight["arrival_datetime"], "%Y-%m-%d %H:%M:%S")

        # 10. Arrival is later than departure.
        assert arrival > departure, f"Flight {flight['flight_id']} arrives before it departs"

        # 11. Actual duration exactly matches the route's scheduled duration.
        actual_minutes = (arrival - departure).total_seconds() / 60
        assert actual_minutes == route["scheduled_duration_minutes"], (
            f"Flight {flight['flight_id']} duration {actual_minutes} does not match "
            f"route {route['route_id']} scheduled duration {route['scheduled_duration_minutes']}"
        )

        # 12. Seats remaining within aircraft capacity.
        capacity = get_aircraft_capacity(flight["aircraft_type_id"], aircraft_types_by_id)
        assert 0 <= flight["seats_remaining"] <= capacity, (
            f"seats_remaining out of range for flight {flight['flight_id']}"
        )

    # 13. Every route appears in flights.csv.
    used_route_ids = {f["route_id"] for f in flights}
    missing_routes = set(routes_by_id) - used_route_ids
    assert not missing_routes, f"Routes with no flights: {missing_routes}"

    # 14 & 15. Flight frequency reflects popularity: High > Medium > Low.
    flights_per_route = {route_id: 0 for route_id in routes_by_id}
    for flight in flights:
        flights_per_route[flight["route_id"]] += 1

    def average_for(popularity):
        route_ids = [r["route_id"] for r in routes if r["route_popularity"] == popularity]
        return sum(flights_per_route[r] for r in route_ids) / len(route_ids)

    avg_high = average_for("High")
    avg_medium = average_for("Medium")
    avg_low = average_for("Low")
    assert avg_high > avg_medium, (
        f"High-popularity routes ({avg_high:.1f} avg) should have more flights than "
        f"Medium ({avg_medium:.1f} avg)"
    )
    assert avg_medium > avg_low, (
        f"Medium-popularity routes ({avg_medium:.1f} avg) should have more flights than "
        f"Low ({avg_low:.1f} avg)"
    )

    # 16. Weekdays and weekends both represented.
    day_types_found = {classify_day_type(f["departure_datetime"]) for f in flights}
    assert {"weekday", "weekend"}.issubset(day_types_found), "Missing weekday/weekend coverage"

    # 17. All four time-of-day categories represented.
    periods_found = {classify_time_of_day(f["departure_datetime"]) for f in flights}
    assert set(TIME_SLOT_NAMES).issubset(periods_found), (
        f"Missing time-of-day coverage: {set(TIME_SLOT_NAMES) - periods_found}"
    )

    # 18. All seasonal categories represented.
    seasons_found = {classify_season(f["departure_datetime"]) for f in flights}
    assert set(SEASON_NAMES).issubset(seasons_found), (
        f"Missing seasonal coverage: {set(SEASON_NAMES) - seasons_found}"
    )

    # 19. All seats-remaining percentage buckets represented.
    expected_bucket_labels = {label for _, _, label in SEAT_BUCKETS}
    buckets_found = {
        classify_seat_bucket(
            f["seats_remaining"], get_aircraft_capacity(f["aircraft_type_id"], aircraft_types_by_id)
        )
        for f in flights
    }
    assert buckets_found == expected_bucket_labels, (
        f"Missing seat-remaining buckets: {expected_bucket_labels - buckets_found}"
    )


def validate_connections(candidates):
    """Checks 20-24: the synthetic schedule demonstrates real connection
    logic - some valid one-stop pairs, and at least one deliberately bad
    example on each side, with no nonsensical results.
    """
    valid = [c for c in candidates if c["classification"] == "Valid"]
    too_short = [c for c in candidates if c["classification"] == "Too Short"]
    too_long = [c for c in candidates if c["classification"] == "Too Long"]

    # 20. Several valid one-stop itineraries exist.
    assert len(valid) >= 3, f"Expected several valid one-stop candidates, found {len(valid)}"

    # 21. At least one candidate below 60 minutes.
    assert len(too_short) >= 1, "Expected at least one too-short candidate connection"

    # 22. At least one candidate above 240 minutes.
    assert len(too_long) >= 1, "Expected at least one too-long candidate connection"

    for candidate in candidates:
        # 23. No negative layover time.
        assert candidate["layover_minutes"] >= 0, "Connection layover must not be negative"
        # 24. No flight connects to itself.
        assert candidate["first_flight_id"] != candidate["second_flight_id"], (
            "A flight cannot connect to itself"
        )


# --------------------------------------------------------------------
# Output
# --------------------------------------------------------------------

def write_csv(aircraft_types, routes, flights):
    """Write all three CSV files, overwriting any existing files."""
    with open(AIRCRAFT_CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["aircraft_type_id", "aircraft_name", "capacity"])
        writer.writeheader()
        writer.writerows(aircraft_types)

    with open(ROUTES_CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "route_id", "origin", "destination", "origin_city",
                "destination_city", "route_popularity", "scheduled_duration_minutes",
            ],
        )
        writer.writeheader()
        writer.writerows(routes)

    with open(FLIGHTS_CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "flight_id", "route_id", "aircraft_type_id",
                "departure_datetime", "arrival_datetime", "seats_remaining",
            ],
        )
        writer.writeheader()
        writer.writerows(flights)


def print_summary(aircraft_types, routes, flights, candidates):
    """Print a readable summary of the generated dataset."""
    aircraft_by_id = {a["aircraft_type_id"]: a for a in aircraft_types}

    print("Generated:")
    print(f"{len(aircraft_types)} aircraft types")
    print(f"{len(routes)} routes")
    print(f"{len(flights)} flights")

    print("\nFlights by route:")
    for route in routes:
        count = sum(1 for f in flights if f["route_id"] == route["route_id"])
        print(f"  {route['origin']} -> {route['destination']}: {count}")

    print("\nFlights by route popularity:")
    for popularity in ["High", "Medium", "Low"]:
        route_ids = {r["route_id"] for r in routes if r["route_popularity"] == popularity}
        count = sum(1 for f in flights if f["route_id"] in route_ids)
        print(f"  {popularity}: {count}")

    print("\nFlights by aircraft type:")
    for aircraft in aircraft_types:
        count = sum(1 for f in flights if f["aircraft_type_id"] == aircraft["aircraft_type_id"])
        print(f"  {aircraft['aircraft_name']}: {count}")

    print("\nFlights by season:")
    for season in SEASON_NAMES:
        count = sum(1 for f in flights if classify_season(f["departure_datetime"]) == season)
        print(f"  {season}: {count}")

    print("\nFlights by time of day:")
    for period in TIME_SLOT_NAMES:
        label = "Overnight / Very Early" if period == "Overnight" else period
        count = sum(1 for f in flights if classify_time_of_day(f["departure_datetime"]) == period)
        print(f"  {label}: {count}")

    print("\nFlights by seat availability:")
    for _, _, label in SEAT_BUCKETS:
        count = sum(
            1 for f in flights
            if classify_seat_bucket(
                f["seats_remaining"], get_aircraft_capacity(f["aircraft_type_id"], aircraft_by_id)
            ) == label
        )
        print(f"  {label}: {count}")

    valid = [c for c in candidates if c["classification"] == "Valid"]
    too_short = [c for c in candidates if c["classification"] == "Too Short"]
    too_long = [c for c in candidates if c["classification"] == "Too Long"]

    print("\nConnection validation:")
    print(f"  Valid one-stop candidate pairs: {len(valid)}")
    print(f"  Too-short candidate pairs: {len(too_short)}")
    print(f"  Too-long candidate pairs: {len(too_long)}")

    print("\nExample valid itineraries:")
    for candidate in valid[:5]:
        arrival_time = datetime.strptime(
            candidate["arrival_at_via"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%H:%M")
        departure_time = datetime.strptime(
            candidate["next_departure"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%H:%M")
        print(f"  {candidate['origin']} -> {candidate['via_airport']} -> {candidate['destination']}")
        print(f"  {candidate['first_flight_id']} + {candidate['second_flight_id']}")
        print(f"  Arrival at {candidate['via_airport']}: {arrival_time}")
        print(f"  Next departure: {departure_time}")
        print(f"  Layover: {int(round(candidate['layover_minutes']))} minutes\n")

    print("All validation checks passed.")


# --------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------

def main():
    aircraft_types = create_aircraft_types()
    aircraft_types_by_id = {a["aircraft_type_id"]: a for a in aircraft_types}
    routes = create_routes()

    flights = generate_flights(routes, aircraft_types_by_id)
    candidates = scan_for_connection_candidates(routes, flights)

    validate_aircraft(aircraft_types, flights)
    validate_routes(routes)
    validate_flights(routes, aircraft_types_by_id, flights)
    validate_connections(candidates)

    write_csv(aircraft_types, routes, flights)
    print_summary(aircraft_types, routes, flights, candidates)


if __name__ == "__main__":
    main()
