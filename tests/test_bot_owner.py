from types import SimpleNamespace as NS

from noshow.bot import is_owner


def update(user_id, chat_type="private"):
    return NS(effective_user=NS(id=user_id), effective_chat=NS(id=999, type=chat_type))


def test_only_the_pinned_owner_in_a_private_chat_is_the_owner(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "42")
    assert is_owner(update(42))
    assert not is_owner(update(7))
    assert not is_owner(update(42, chat_type="group"))


def test_nobody_is_owner_until_one_is_pinned(monkeypatch):
    monkeypatch.delenv("TELEGRAM_OWNER_ID", raising=False)
    assert not is_owner(update(42))


from datetime import date, datetime  # noqa: E402

from noshow.bot import seconds_until, summary  # noqa: E402


def g(name, risk, day, reasons=(), flagged=True):
    return {"flagged": flagged, "risk": risk, "reasons": list(reasons),
            "booking": {"guest": name, "arrival": date(2017, 3, day)}}


def test_summary_is_short_names_who_to_start_with_and_what_they_share():
    agent = {"label": "Booked through agent 9", "rate": 0.40}
    guests = [g("Ana Silva", 0.64, 6, [agent]), g("Ben Carter", 0.51, 7, [agent]), g("Cy Lee", 0.44, 7, [agent]),
              g("Dee Moss", 0.31, 8), g("Chloe Nguyen", 0.1, 7, flagged=False)]
    assert summary(guests, 0.30, "http://localhost:8000", "$1,834") == (
        "Good morning. 4 guests arriving in the next 3 days might not show: $1,834 of bookings.\n\n"
        "Start with Ana Silva (64%), Ben Carter (51%) and Cy Lee (44%), plus 1 more.\n"
        "What most of them share: booked through agent 9 (40% of similar past guests cancelled).\n\n"
        "Draft a message or leave each one: http://localhost:8000")


def test_summary_on_a_quiet_morning_says_so():
    assert summary([g("Chloe Nguyen", 0.1, 7, flagged=False)], 0.30, "http://x", "$0.00") == (
        "Good morning. None of the guests arriving in the next 3 days look likely to cancel. http://x")


def test_the_ping_waits_until_the_next_morning_time():
    assert seconds_until("08:00", datetime(2026, 10, 14, 7, 0)) == 3600
    assert seconds_until("08:00", datetime(2026, 10, 14, 9, 0)) == 23 * 3600
