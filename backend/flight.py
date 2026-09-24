"""Flight model built from one row of the SQLite flights table."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True)
class Flight:
    flight_id: str
    origin: str
    destination: str
    flight_date: str
    departure_time: str
    route_popularity: str
    seat_capacity: int
    seats_remaining: int
    base_fare: float
    minimum_fare: float
    maximum_fare: float

    @classmethod
    def from_row(cls, row):
        """Use the column order returned by database.db.get_flight_by_id."""
        if row is None:
            raise ValueError("Flight row is missing")
        if len(row) != 11:
            raise ValueError("Flight row must contain 11 columns")
        return cls(*row)

    def __post_init__(self):
        if not self.flight_id or not self.origin or not self.destination:
            raise ValueError("Flight ID, origin, and destination are required")
        if self.origin == self.destination:
            raise ValueError("Origin and destination must differ")
        departure = datetime.strptime(f"{self.flight_date} {self.departure_time}", "%Y-%m-%d %H:%M")
        if (departure.strftime("%Y-%m-%d") != self.flight_date
                or departure.strftime("%H:%M") != self.departure_time):
            raise ValueError("flight_date must use YYYY-MM-DD and departure_time must use HH:MM")
        if self.route_popularity not in {"High", "Medium", "Low"}:
            raise ValueError("Invalid route popularity")
        # bool is an int subclass, but True/False are not valid seat counts.
        for name in ("seat_capacity", "seats_remaining"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if self.seat_capacity <= 0 or not 0 <= self.seats_remaining <= self.seat_capacity:
            raise ValueError("Seats must be between zero and capacity")
        for name in ("minimum_fare", "base_fare", "maximum_fare"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number")
            try:
                finite = isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"{name} must be a finite number")
        if not 0 <= self.minimum_fare <= self.base_fare <= self.maximum_fare:
            raise ValueError("Fare bounds are invalid")

    @property
    def departure(self):
        return datetime.strptime(f"{self.flight_date} {self.departure_time}", "%Y-%m-%d %H:%M")

    @property
    def seat_fraction(self):
        return self.seats_remaining / self.seat_capacity
