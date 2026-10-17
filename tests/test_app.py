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


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    """The hosted demo: no dataset, no TabPFN, no Ollama; each visitor gets their own copy of the demo morning."""
    monkeypatch.setattr(desk, "HOSTED", True)
    monkeypatch.setattr(desk, "load", lambda: (_ for _ in ()).throw(AssertionError("hosted must not load the dataset")))
    api.state.desk = desk.app(tmp_path / "desk.sqlite", writer=lambda b: pytest.fail("hosted has no Ollama"))
    return lambda: TestClient(api)


def test_hosted_visitors_each_get_their_own_desk(hosted):
    a, b = hosted(), hosted()
    day = a.get("/api/day").json()
    assert (len(day["guests"]), day["at_risk"]["guests"], day["drafts"]) == (50, 7, "browser")
    chloe = next(g for g in day["guests"] if g["booking"]["guest"] == "Chloe Nguyen")
    assert a.post(f"/api/guests/{chloe['id']}/leave").json()["outcome"] == "left"
    assert b.post(f"/api/guests/{chloe['id']}/leave").status_code == 404   # not b's guest
    theirs = next(g for g in b.get("/api/day").json()["guests"] if g["booking"]["guest"] == "Chloe Nguyen")
    assert theirs["stage"] == "choose" and theirs["id"] != chloe["id"]
    assert len(b.get("/api/replay/2017").json()["mornings"]) == 30   # from the snapshot, no dataset


def test_hosted_drafts_come_from_the_browser_or_the_recorded_copy(hosted):
    c = hosted()
    guests = {g["booking"]["guest"]: g for g in c.get("/api/day").json()["guests"]}
    ana, chloe = guests["Ana Silva"]["id"], guests["Chloe Nguyen"]["id"]
    brief = c.get(f"/api/guests/{ana}/brief").json()
    assert "Total: $88.00" in brief["brief"] and brief["system"].startswith("You write") and brief["recorded"]["problems"] == []
    g = c.post(f"/api/guests/{ana}/draft", json={"text": "Hi Ana, 1 night, $99.00 in total. Reply YES."}).json()
    assert g["stage"] == "review" and g["by"] == "browser" and g["problems"]   # checked like any draft
    g = c.post(f"/api/guests/{chloe}/draft", json={"text": "ignored", "by": "recorded"}).json()
    assert g["by"] == "recorded" and g["draft"] == c.get(f"/api/guests/{chloe}/brief").json()["recorded"]["text"]
    assert g["problems"] == []


def test_the_snapshot_matches_what_the_desk_works_out_live():
    snap = desk.snapshot()
    assert snap["roi"] == desk.live_roi()
    assert snap["replay"]["2017"] == desk.live_replay("2017") and snap["replay"]["2016"] == desk.live_replay("2016")
    assert sum(s["flagged"] for s in snap["morning"]) == 7 and len(snap["recorded"]) == 7


def test_hosted_refuses_odd_cookies_blank_drafts_and_the_morning_button(hosted):
    c = hosted()
    c.cookies.set("desk", "a" * 4000)
    day = c.get("/api/day").json()
    assert len(day["guests"][0]["id"].split("~")[0]) == 16   # a fresh id, not the long one sent
    ana = next(g["id"] for g in day["guests"] if g["booking"]["guest"] == "Ana Silva")
    assert c.post(f"/api/guests/{ana}/draft", json={"text": "   "}).status_code == 422
    assert c.post(f"/api/guests/{ana}/draft", json={"by": "recorded"}).json()["stage"] == "review"   # still usable
    assert c.post("/api/morning").status_code == 404


def test_hosted_stops_making_desks_past_the_cap(hosted, monkeypatch):
    monkeypatch.setattr(desk, "MAX_VISITORS", 2)
    assert hosted().get("/api/day").status_code == 200 and hosted().get("/api/day").status_code == 200
    assert hosted().get("/api/day").status_code == 503


def test_a_draft_that_failed_half_way_can_be_tried_again(tmp_path):
    tries = []
    def flaky(brief):
        tries.append(brief)
        if len(tries) == 1:
            raise ConnectionError("Ollama isn't running")
        return GOOD
    graph = desk.app(tmp_path / "desk.sqlite", writer=flaky, sender=lambda b, t: {})
    graph.invoke({"booking": {**booking(1, "Ana Silva"), "due": True}, "risk": 0.6, "flagged": True, "reasons": []},
                 {"configurable": {"thread_id": f"{desk.DAY}-1"}})
    with pytest.raises(ConnectionError):
        desk.act(f"{desk.DAY}-1", "draft", desk=graph)
    assert desk.act(f"{desk.DAY}-1", "draft", desk=graph)["stage"] == "review"


def test_checking_an_edit_reports_a_wrong_fact_and_sends_nothing(client):
    url = drafted(client).replace("/send", "/check")
    r = client.post(url, json={"text": "Hi Ana, see you 25 December. Total $1."})
    assert r.status_code == 200 and "amount $1 is not the total $286.50" in r.json()["problems"]
    assert client.sent == [] and client.get("/api/day").json()["guests"][1]["stage"] == "review"   # nothing moved
    assert client.post(url, json={"text": GOOD}).json()["problems"] == []
    assert client.post(url, json={"text": "  "}).json()["problems"] == ["the message is empty"]


def test_an_edit_can_only_be_checked_while_its_draft_waits_for_send(client):
    assert client.post(f"/api/guests/{desk.DAY}-1/check", json={"text": GOOD}).status_code == 409   # no draft yet


def test_hosted_visitors_cannot_check_each_others_drafts(hosted):
    a, b = hosted(), hosted()
    chloe = next(g for g in a.get("/api/day").json()["guests"] if g["booking"]["guest"] == "Chloe Nguyen")["id"]
    a.post(f"/api/guests/{chloe}/draft", json={"text": "ignored", "by": "recorded"})
    assert a.post(f"/api/guests/{chloe}/check", json={"text": "Total $1."}).json()["problems"]
    b.get("/api/day")
    assert b.post(f"/api/guests/{chloe}/check", json={"text": "Total $1."}).status_code == 404   # not b's guest
