"""Update saved minimum fares to 80% without resetting flight or seat edits.

Run from the project root: python -m database.migrate_minimum_fares
"""

from decimal import Decimal, ROUND_HALF_UP

from .db import get_connection


def migrate_minimum_fares():
    """Apply the new policy in one transaction; return the changed row count."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT flight_id, base_fare, minimum_fare FROM flights"
        ).fetchall()
        changes = []
        for flight_id, base_fare, old_minimum in rows:
            minimum = float((Decimal(str(base_fare)) * Decimal("0.80")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ))
            if minimum != old_minimum:
                changes.append((minimum, flight_id))
        connection.executemany(
            "UPDATE flights SET minimum_fare = ? WHERE flight_id = ?", changes
        )
    return len(changes)


if __name__ == "__main__":
    print(f"Updated minimum fares for {migrate_minimum_fares()} flights to 80% of base fare.")
