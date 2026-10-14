"""Plain reasons a booking was flagged, from the motel's own past bookings. Code computes the rates;
the drafting model never sees them. These describe past guests like this one, not TabPFN's internals."""
import pandas as pd

from noshow.data import TARGET

MIN_GROUP = 30     # fewer past bookings than this and the rate is mostly luck
MIN_GAP = 0.05     # the group must cancel at least 5 points more than everyone
MAX_REASONS = 3

LEAD_BANDS = [(7, "a week or less"), (30, "1 to 4 weeks"), (90, "1 to 3 months"),
              (180, "3 to 6 months"), (365, "6 to 12 months"), (float("inf"), "over a year")]
CHANNELS = {"Online TA": "an online travel agent", "Offline TA/TO": "a travel agent or tour operator",
            "Groups": "a group organiser", "Direct": "the motel directly", "Corporate": "a company account",
            "Complementary": "a complimentary stay", "Aviation": "an airline crew booking"}


MEALS = {"SC": ("Room only, no meals", "past room-only bookings"), "BB": ("Bed and breakfast", "past B&B bookings"),
         "HB": ("Half board", "past half-board bookings"), "FB": ("Full board", "past full-board bookings")}


def _agent(v, g) -> tuple[str, str]:
    # The dataset numbers its agents; a real motel would see the name (e.g. the booking site)
    if g == "0":
        return "Booked without an agent", "past bookings without one"
    if g == "other":
        return "Booked through a small agent", "past bookings from small agents"
    return f"Booked through agent {g}", "past bookings from that agent"


def _band(days) -> str:
    return next(label for top, label in LEAD_BANDS if days <= top)


def _channel(seg) -> str:
    return CHANNELS.get(str(seg), str(seg))


# column, how a value is grouped, (label for this booking, who the past group is); max 3 shown, biggest first
FACTORS = [
    ("lead_time", _band, lambda v, g: (f"Booked {v} days ahead", f"past guests who booked {g} ahead")),
    ("previous_cancellations", lambda v: v > 0, lambda v, g: (
        (f"Cancelled {v} booking{'s' if v > 1 else ''} before", "past guests with an earlier cancellation")
        if g else ("No earlier cancellations", "past guests with none"))),
    ("market_segment", _channel, lambda v, g: (f"Booked via {g}", "past bookings through that channel")),
    ("agent", str, _agent),
    ("meal", str, lambda v, g: MEALS.get(g, ("Meal plan not recorded", "past bookings without one"))),
    ("is_repeated_guest", lambda v: v == 1, lambda v, g: (
        ("Has stayed before", "past returning guests") if g else ("First stay with you", "past first-time guests"))),
    ("total_of_special_requests", lambda v: v > 0, lambda v, g: (
        ("Made special requests", "past guests who made some") if g
        else ("No special requests", "past guests who made none"))),
]


def reasons(booking: pd.Series, history: pd.DataFrame) -> list[dict]:
    past = history[history.deposit_type == "No Deposit"]   # prepaid cancellations cost the owner nothing
    base = round(float(past[TARGET].mean()), 2)
    found = []
    for col, group, say in FACTORS:
        value = booking[col]
        g = group(value)
        same = past[past[col].map(group).astype(object) == g]
        if len(same) < MIN_GROUP:
            continue
        rate = round(float(same[TARGET].mean()), 2)
        if rate - base >= MIN_GAP:
            label, who = say(value, g)
            found.append({"label": label, "who": who, "rate": rate, "base": base, "n": len(same),
                          "text": f"{label}: {who} cancelled {rate:.0%} of the time (all past guests: {base:.0%})."})
    return sorted(found, key=lambda r: -r["rate"])[:MAX_REASONS]
