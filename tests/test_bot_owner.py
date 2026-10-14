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


def test_summary_lists_flagged_guests_with_their_top_reason():
    guests = [g("Ana Silva", 0.64, 6, [{"label": "Booked 210 days ahead", "rate": 0.45}]),
              g("Ben Carter", 0.31, 7), g("Chloe Nguyen", 0.1, 7, flagged=False)]
    assert summary(guests, 0.30, "http://localhost:8000") == (
        "Good morning. 2 of 3 arriving guests are 30% or more likely to cancel:\n\n"
        "• Ana Silva, 64%, arrives Mon 6 Mar. Booked 210 days ahead (45% of similar past guests cancelled)\n"
        "• Ben Carter, 31%, arrives Tue 7 Mar\n\n"
        "Draft a message or leave each one: http://localhost:8000")


def test_summary_on_a_quiet_morning_says_so():
    assert summary([g("Chloe Nguyen", 0.1, 7, flagged=False)], 0.30, "http://x") == (
        "Good morning. None of the 1 arriving guests is 30% or more likely to cancel. http://x")


def test_the_ping_waits_until_the_next_morning_time():
    assert seconds_until("08:00", datetime(2026, 10, 14, 7, 0)) == 3600
    assert seconds_until("08:00", datetime(2026, 10, 14, 9, 0)) == 23 * 3600
