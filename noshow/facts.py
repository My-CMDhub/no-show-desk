"""Everything a message states as fact is worked out here, in code. The model only phrases it."""
from datetime import date, timedelta

FREE_CANCEL_DAYS = 2   # motel policy: free cancellation until 2 days before arrival


def work_out_facts(b: dict) -> dict:
    arrival: date = b["arrival"]
    nights = int(b["stays_in_weekend_nights"] + b["stays_in_week_nights"])
    return {
        "guest": b["guest"],
        "room": b["reserved_room_type"],
        "arrival": arrival,
        "departure": arrival + timedelta(days=nights),
        "nights": nights,
        "total": f"${b['adr'] * nights:,.2f}",
        "free_cancel_until": arrival - timedelta(days=FREE_CANCEL_DAYS),
    }


def spoken(d: date) -> str:
    return f"{d:%A} {d.day} {d:%B}"


def as_note(f: dict) -> str:
    """The facts as the drafting model sees them."""
    return (f"Guest: {f['guest']}\nRoom type: {f['room']}\n"
            f"Arrival: {spoken(f['arrival'])}\nDeparture: {spoken(f['departure'])}\n"
            f"Nights: {f['nights']}\nTotal: {f['total']}\n"
            f"Free cancellation until: {spoken(f['free_cancel_until'])}")
