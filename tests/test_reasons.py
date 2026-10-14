import pandas as pd

from noshow.reasons import reasons

NEUTRAL = {"deposit_type": "No Deposit", "previous_cancellations": 0, "market_segment": "Direct",
           "is_repeated_guest": 0, "total_of_special_requests": 1, "agent": "0", "meal": "BB"}


def rows(n, cancelled, **fields):
    return [{**NEUTRAL, "lead_time": 3, **fields, "is_canceled": int(i < cancelled)} for i in range(n)]


# 40 early bookers cancel 50%, 60 last-minute bookers cancel 10%: overall 26%
HISTORY = pd.DataFrame(rows(40, 20, lead_time=200) + rows(60, 6))


def booking(**fields):
    return pd.Series({**NEUTRAL, "lead_time": 3, **fields})


def test_an_early_booking_gets_the_lead_time_reason_in_plain_words():
    [r] = reasons(booking(lead_time=210), HISTORY)
    assert r["text"] == ("Booked 210 days ahead: past guests who booked 6 to 12 months ahead "
                         "cancelled 50% of the time (all past guests: 26%).")
    assert (r["rate"], r["base"], r["n"]) == (0.5, 0.26, 40)


def test_a_group_that_cancels_less_than_usual_is_not_a_reason():
    assert reasons(booking(lead_time=2), HISTORY) == []


def test_a_group_smaller_than_30_bookings_is_not_trusted():
    small = pd.DataFrame(rows(29, 29, lead_time=200) + rows(71, 0))
    assert reasons(booking(lead_time=210), small) == []


def test_prepaid_bookings_in_history_are_ignored():
    prepaid = pd.DataFrame(rows(50, 50, deposit_type="Non Refund"))
    [r] = reasons(booking(lead_time=210), pd.concat([HISTORY, prepaid]))
    assert r["base"] == 0.26


def test_at_most_three_reasons_biggest_gap_first():
    risky = dict(lead_time=200, previous_cancellations=1, market_segment="Online TA",
                 is_repeated_guest=0, total_of_special_requests=0)
    history = pd.DataFrame(rows(40, 36, **risky) + rows(40, 40, previous_cancellations=1) + rows(160, 16))
    found = reasons(booking(**risky), history)   # four factors qualify; earlier cancellations cancel most
    assert len(found) == 3 and [r["rate"] for r in found] == sorted([r["rate"] for r in found], reverse=True)
    assert found[0]["label"] == "Cancelled 1 booking before" and found[0]["rate"] == 0.95


def test_the_booking_agent_and_room_only_can_be_reasons():
    history = pd.DataFrame(rows(40, 20, agent="9", meal="SC") + rows(60, 6))
    found = {r["label"]: r["who"] for r in reasons(booking(agent="9", meal="SC"), history)}
    assert found == {"Booked through travel agent #9": "past bookings from that agent",
                     "Room only, no meals": "past room-only bookings"}
