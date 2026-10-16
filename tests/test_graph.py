from datetime import date

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from noshow.graph import build

BOOKING = {"arrival": date(2017, 3, 10), "stays_in_weekend_nights": 2, "stays_in_week_nights": 1,
           "adr": 95.5, "reserved_room_type": "A", "guest": "Ana Silva"}
GOOD = ("Hi Ana, 3 nights from Friday 10 March to Monday 13 March, $286.50 in total. "
        "Cancel free until Wednesday 8 March. Reply YES to keep the room.")


def run(writer, risk=0.8, thread="t1", sent=None):
    sender = lambda booking, text: (sent.append(text) if sent is not None else None) or {"channel": "email"}
    app = build(writer=writer, sender=sender, checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": thread}}
    return app, cfg, app.invoke({"booking": BOOKING, "risk": risk, "flagged": risk >= 0.3}, cfg)


def stage(out):
    return out["__interrupt__"][0].value["stage"]


def test_unflagged_guest_ends_without_pausing():
    calls = []
    _, _, out = run(lambda b: calls.append(b) or GOOD, risk=0.2)
    assert calls == [] and "__interrupt__" not in out and "draft" not in out


def test_flagged_guest_waits_for_the_owner_before_any_draft():
    calls = []
    _, _, out = run(lambda b: calls.append(b) or GOOD)
    assert stage(out) == "choose" and calls == []


def test_leave_ends_without_drafting():
    calls = []
    app, cfg, _ = run(lambda b: calls.append(b) or GOOD)
    done = app.invoke(Command(resume="leave"), cfg)
    assert done["outcome"] == "left" and calls == [] and "draft" not in done


def test_draft_pauses_again_for_review_with_the_check_result():
    app, cfg, _ = run(lambda b: GOOD)
    out = app.invoke(Command(resume="draft"), cfg)
    assert stage(out) == "review" and out["draft"] == GOOD and out["problems"] == []


def test_send_delivers_the_draft_and_records_how():
    sent = []
    app, cfg, _ = run(lambda b: GOOD, sent=sent)
    app.invoke(Command(resume="draft"), cfg)
    done = app.invoke(Command(resume="send"), cfg)
    assert sent == [GOOD] and done["outcome"] == "sent" and done["sent"] == {"channel": "email"}


def test_owner_edit_is_what_gets_sent():
    sent = []
    app, cfg, _ = run(lambda b: GOOD, sent=sent)
    app.invoke(Command(resume="draft"), cfg)
    done = app.invoke(Command(resume={"decision": "send", "text": "edited"}), cfg)
    assert sent == ["edited"] and done["final"] == "edited"


def test_reject_discards_the_draft_and_sends_nothing():
    sent = []
    app, cfg, _ = run(lambda b: GOOD, sent=sent)
    app.invoke(Command(resume="draft"), cfg)
    done = app.invoke(Command(resume="reject"), cfg)
    assert sent == [] and done["outcome"] == "rejected" and not done.get("final")


def test_a_wrong_draft_is_redrafted_once():
    drafts = iter([GOOD.replace("$286.50", "$250.00"), GOOD])
    app, cfg, _ = run(lambda b: next(drafts))
    out = app.invoke(Command(resume="draft"), cfg)
    assert out["attempts"] == 2 and out["problems"] == []


def test_still_wrong_after_retry_reaches_owner_flagged():
    app, cfg, _ = run(lambda b: GOOD.replace("$286.50", "$250.00"))
    out = app.invoke(Command(resume="draft"), cfg)
    assert out["attempts"] == 2 and out["problems"] == ["amount $250.00 is not the total $286.50"]


def test_the_brief_carries_facts_worked_out_in_code():
    seen = []
    app, cfg, _ = run(lambda b: seen.append(b) or GOOD)
    app.invoke(Command(resume="draft"), cfg)
    assert "Total: $286.50" in seen[0] and "Free cancellation until: Wednesday 8 March" in seen[0]


def test_a_draft_written_in_the_browser_is_checked_and_never_redrafted_here():
    calls = []
    app, cfg, _ = run(lambda b: calls.append(b) or GOOD)
    out = app.invoke(Command(resume={"decision": "draft", "text": GOOD, "by": "browser"}), cfg)
    assert stage(out) == "review" and out["draft"] == GOOD and out["problems"] == [] and out["by"] == "browser"
    app, cfg, _ = run(lambda b: calls.append(b) or GOOD, thread="t2")
    out = app.invoke(Command(resume={"decision": "draft", "text": GOOD.replace("$286.50", "$290.00"), "by": "browser"}), cfg)
    assert stage(out) == "review" and out["problems"] and calls == []   # no model here: the owner sees the problem
