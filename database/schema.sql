-- Potter Airlines relational schema.
-- Tables are listed in dependency order: aircraft_types and routes have no
-- foreign keys, flights depends on both, and bookings depends on flights.

CREATE TABLE IF NOT EXISTS aircraft_types (
    aircraft_type_id TEXT PRIMARY KEY,
    aircraft_name TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    CHECK (capacity > 0)
);

CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    origin_city TEXT NOT NULL,
    destination_city TEXT NOT NULL,
    route_popularity TEXT NOT NULL,
    scheduled_duration_minutes INTEGER NOT NULL,
    CHECK (origin <> destination),
    CHECK (scheduled_duration_minutes > 0),
    CHECK (route_popularity IN ('High', 'Medium', 'Low'))
);

CREATE TABLE IF NOT EXISTS flights (
    flight_id TEXT PRIMARY KEY,
    route_id TEXT NOT NULL,
    aircraft_type_id TEXT NOT NULL,
    departure_datetime TEXT NOT NULL,
    arrival_datetime TEXT NOT NULL,
    seats_remaining INTEGER NOT NULL,
    CHECK (seats_remaining >= 0),
    -- Capacity is not duplicated here; look it up via aircraft_type_id.
    FOREIGN KEY (route_id) REFERENCES routes (route_id),
    FOREIGN KEY (aircraft_type_id) REFERENCES aircraft_types (aircraft_type_id)
);

-- Bookings starts empty. It exists now so the project has a table ready
-- for INSERT / SELECT / UPDATE / DELETE work in the next stage.
CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    number_of_passengers INTEGER NOT NULL,
    booking_datetime TEXT NOT NULL,
    price_paid REAL NOT NULL,
    CHECK (number_of_passengers > 0),
    CHECK (price_paid >= 0),
    FOREIGN KEY (flight_id) REFERENCES flights (flight_id)
);
