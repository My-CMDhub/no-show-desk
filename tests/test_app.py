from datetime import date

import pytest
from fastapi.testclient import TestClient

from noshow import desk
from noshow.app import api

GOOD = ("Hi Ana, 3 nights from Friday 10 March to Monday 13 March, $286.50 in total. "
        "Cancel free until Wednesday 8 March. Reply YES to keep the room.")


def booking(n, name):
    return {"id": f"{desk.DAY}-{n}", "guest": name, "contact": {"channel": "email", "to": "a.s@example.com"},
            "arrival": date(2017, 3, 10), "stays_in_weekend_nights": 2, "stays_in_week_nights": 1,
            "adr": 95.5, "reserved_room_type": "A"}


@pytest.fixture
def client(tmp_path):
    sent = []
    graph = desk.app(tmp_path / "desk.sqlite", writer=lambda b: GOOD,
                     sender=lambda b, text: sent.append(text) or {**b["contact"], "at": "09:14", "demo": True})
    for n, name, risk, due in [(1, "Ana Silva", 0.64, True), (2, "Ben Carter", 0.12, True), (3, "Cy Lee", 0.7, False)]:
        graph.invoke({"booking": {**booking(n, name), "due": due}, "risk": risk, "flagged": due and risk >= desk.FLAG_LINE,
                      "reasons": []}, {"configurable": {"thread_id": f"{desk.DAY}-{n}"}})
    api.state.desk = graph
    c = TestClient(api)
    c.sent = sent
    return c


def test_the_day_lists_every_guest_riskiest_first_with_where_each_stands(client):
    day = client.get("/api/day").json()
    assert [(g["booking"]["guest"], g["stage"]) for g in day["guests"]] == [
        ("Cy Lee", None), ("Ana Silva", "choose"), ("Ben Carter", None)]   # a later booking is listed, never flagged
    assert day["line"] == 0.30 and day["roi"]["per_morning"] == 7.0
    assert day["at_risk"] == {"guests": 1, "total": "$286.50"}   # flagged guests due in the window, worked out in code


def test_draft_then_send_records_a_mock_delivery(client):
    g = client.post(f"/api/guests/{desk.DAY}-1/draft").json()
    assert g["stage"] == "review" and g["draft"] == GOOD and g["problems"] == []
    g = client.post(f"/api/guests/{desk.DAY}-1/send", json={"text": "edited"}).json()
    assert g["outcome"] == "sent" and g["sent"]["demo"] is True and client.sent == ["edited"]


def test_leave_marks_the_guest_without_a_draft(client):
    g = client.post(f"/api/guests/{desk.DAY}-1/leave").json()
    assert g["outcome"] == "left" and "draft" not in g


def test_a_choice_the_run_is_not_waiting_for_is_refused(client):
    assert client.post(f"/api/guests/{desk.DAY}-1/send").status_code == 409     # no draft yet
    assert client.post(f"/api/guests/{desk.DAY}-2/draft").status_code == 409    # not flagged
    assert client.post(f"/api/guests/{desk.DAY}-99/leave").status_code == 409   # no such booking
    assert client.post(f"/api/guests/{desk.DAY}-1/explode").status_code == 409


def test_roi_from_the_30_test_mornings():
    r = desk.roi()
    assert (r["mornings"], r["per_morning"], r["share_cancelled"], r["caught_per_morning"]) == (30, 7.0, 0.53, 3.7)
    assert (r["caught"], r["cancelled"]) == (111, 172)
    assert r["caught_value_per_morning"] == "$2,378"   # whole-stay totals of flagged guests who did cancel
