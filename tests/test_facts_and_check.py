from datetime import date

from noshow.check import check_draft
from noshow.facts import work_out_facts

BOOKING = {"arrival": date(2017, 3, 10), "stays_in_weekend_nights": 2, "stays_in_week_nights": 1,
           "adr": 95.5, "reserved_room_type": "A", "guest": "Ana Silva"}


def test_facts_are_computed_in_code():
    f = work_out_facts(BOOKING)
    assert f["nights"] == 3
    assert f["departure"] == date(2017, 3, 13)
    assert f["total"] == "$286.50"
    assert f["free_cancel_until"] == date(2017, 3, 8)   # 2 days before arrival


def draft(text):
    return check_draft(text, work_out_facts(BOOKING))


GOOD = ("Hi Ana, a quick check on your stay: 3 nights from Friday 10 March to Monday 13 March, "
        "$286.50 in total. You can cancel free of charge until Wednesday 8 March. Reply YES to confirm.")


def test_a_correct_draft_passes():
    assert draft(GOOD) == []


def test_a_wrong_total_fails():
    assert draft(GOOD.replace("$286.50", "$286.00")) == ["amount $286.00 is not the total $286.50"]


def test_an_invented_deposit_fails():
    assert draft(GOOD + " A $50 deposit holds the room.") == ["amount $50 is not the total $286.50"]


def test_a_wrong_date_fails():
    problems = draft(GOOD.replace("Monday 13 March", "Sunday 12 March"))
    assert problems == ["date 12 March is not arrival, departure or free-cancel date"]


def test_the_wrong_number_of_nights_fails():
    assert draft(GOOD.replace("3 nights", "2 nights")) == ["says 2 nights, booking is 3"]


def test_missing_total_fails():
    assert draft(GOOD.replace("$286.50 in total. ", "")) == ["total $286.50 not mentioned"]


def test_date_formats_the_model_likes_are_read():
    ok = GOOD.replace("10 March", "March 10th").replace("8 March", "the 8th of March")
    assert draft(ok) == []
