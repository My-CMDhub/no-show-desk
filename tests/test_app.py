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
    mine = GOOD.replace("Hi Ana", "Hello Ana")
    g = client.post(f"/api/guests/{desk.DAY}-1/send", json={"text": mine}).json()
    assert g["outcome"] == "sent" and g["sent"]["demo"] is True and client.sent == [mine]


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
    assert r["random_caught_per_morning"] == 2.1      # the same number of guests picked at random


def drafted(client):
    client.post(f"/api/guests/{desk.DAY}-1/draft")
    return f"/api/guests/{desk.DAY}-1/send"


def test_an_edit_with_a_wrong_fact_needs_a_second_yes(client):
    url = drafted(client)
    r = client.post(url, json={"text": "Hi Ana, see you 25 December. Total $1."})
    assert r.status_code == 422 and "amount $1 is not the total $286.50" in r.json()["detail"]["problems"]
    assert client.sent == []
    g = client.post(url, json={"text": "Hi Ana, see you 25 December. Total $1.", "anyway": True}).json()
    assert g["outcome"] == "sent" and client.sent == ["Hi Ana, see you 25 December. Total $1."]


def test_a_blank_message_is_refused(client):
    r = client.post(drafted(client), json={"text": "   \n "})
    assert r.status_code == 422 and client.sent == []


def test_two_sends_at_the_same_moment_send_once(tmp_path):
    import threading
    import time
    sent = []
    graph = desk.app(tmp_path / "d.sqlite", writer=lambda b: GOOD,
                     sender=lambda b, text: time.sleep(0.2) or sent.append(text) or {"channel": "email"})
    graph.invoke({"booking": booking(1, "Ana Silva"), "risk": 0.6, "flagged": True, "reasons": []},
                 {"configurable": {"thread_id": "T"}})
    desk.act("T", "draft", desk=graph)
    def send():
        try:
            desk.act("T", "send", desk=graph)
        except ValueError:
            pass
    threads = [threading.Thread(target=send) for _ in range(3)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sent == [GOOD]


def test_a_reason_every_flagged_guest_shares_is_said_once():
    agent = {"label": "Booked through travel agent #9", "rate": 0.4}
    room = {"label": "Room only, no meals", "rate": 0.34}
    guests = [{"flagged": True, "reasons": [agent, room]}, {"flagged": True, "reasons": [agent]},
              {"flagged": False, "reasons": [room]}]
    assert desk.shared_reasons(guests) == [agent]
    assert desk.shared_reasons(guests[:1]) == []   # one guest has nothing to share with


def test_the_page_font_ships_with_the_app(client):
    r = client.get("/fonts/overpass-latin.woff2")
    assert r.status_code == 200 and r.content[:4] == b"wOF2"
    assert "fonts.googleapis.com" not in client.get("/").text


def test_replay_gives_back_the_stored_mornings_with_their_real_outcomes(client):
    year = client.get("/api/replay/2017").json()
    guests = [g for m in year["mornings"] for g in m["guests"]]
    flagged = [g for g in guests if g["risk"] >= 0.30]
    assert (len(year["mornings"]), len(guests)) == (30, 600)
    assert (sum(g["cancelled"] for g in flagged), len(flagged), sum(g["cancelled"] for g in guests)) == (111, 210, 172)
    demo = next(m for m in year["mornings"] if m["day"] == desk.DAY)
    chloe = demo["guests"][2]   # the same guest, id and score as on the demo morning's Today board
    assert (chloe["name"], chloe["id"], chloe["cancelled"]) == ("Chloe Nguyen", f"{desk.DAY}-{chloe['row']}", 1)
    assert round(chloe["risk"], 2) == 0.75 and chloe["nights"] > 0 and chloe["total"] > 0


def test_replay_of_the_year_the_line_was_checked_on(client):
    year = client.get("/api/replay/2016").json()
    flagged = [g for m in year["mornings"] for g in m["guests"] if g["risk"] >= 0.30]
    assert (sum(g["cancelled"] for g in flagged), len(flagged)) == (92, 163)
    assert client.get("/api/replay/2015").status_code == 404
