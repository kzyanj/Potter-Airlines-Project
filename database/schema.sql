-- The source CSV has one row per scheduled flight.
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
