from datetime import date

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from noshow.graph import build

BOOKING = {"arrival": date(2017, 3, 10), "stays_in_weekend_nights": 2, "stays_in_week_nights": 1,
           "adr": 95.5, "reserved_room_type": "A", "guest": "Ana Silva"}
GOOD = ("Hi Ana, 3 nights from Friday 10 March to Monday 13 March, $286.50 in total. "
        "Cancel free until Wednesday 8 March. Reply YES to keep the room.")


def run(writer, risk=0.8, thread="t1"):
    app = build(writer=writer, checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": thread}}
    return app, cfg, app.invoke({"booking": BOOKING, "risk": risk}, cfg)


def test_low_risk_gets_no_draft():
    calls = []
    _, _, out = run(lambda b: calls.append(b) or GOOD, risk=0.2)
    assert calls == [] and "draft" not in out


def test_a_good_draft_pauses_for_the_owner_then_saves_on_approve():
    app, cfg, out = run(lambda b: GOOD)
    assert out["__interrupt__"][0].value["problems"] == []
    done = app.invoke(Command(resume="approve"), cfg)
    assert done["final"] == GOOD and done["attempts"] == 1


def test_a_wrong_draft_is_redrafted_once():
    drafts = iter([GOOD.replace("$286.50", "$250.00"), GOOD])
    _, _, out = run(lambda b: next(drafts))
    assert out["attempts"] == 2 and out["__interrupt__"][0].value["problems"] == []


def test_still_wrong_after_retry_reaches_owner_flagged():
    _, _, out = run(lambda b: GOOD.replace("$286.50", "$250.00"))
    assert out["attempts"] == 2
    assert out["__interrupt__"][0].value["problems"] == ["amount $250.00 is not the total $286.50"]


def test_the_brief_carries_facts_worked_out_in_code():
    seen = []
    run(lambda b: seen.append(b) or GOOD)
    assert "Total: $286.50" in seen[0] and "Free cancellation until: Wednesday 8 March" in seen[0]


def test_owner_edit_replaces_the_draft():
    app, cfg, _ = run(lambda b: GOOD)
    done = app.invoke(Command(resume={"decision": "edit", "text": "edited"}), cfg)
    assert done["decision"] == "edit" and done["final"] == "edited"
