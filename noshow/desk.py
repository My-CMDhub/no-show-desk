"""The morning run: score the demo motel's upcoming bookings in one TabPFN call, then start one graph
run per booking. Guests at or over the line pause, waiting for the owner to press Draft or Leave.

Run from the terminal: .venv/bin/python -m noshow.desk 2017-03-06
"""
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from noshow.data import FEATURES, TARGET, load
from noshow.graph import build
from noshow.facts import work_out_facts
from noshow.reasons import CHANNELS, reasons

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/desk.sqlite"
OUTBOX = ROOT / "data/outbox.jsonl"
RISKS = ROOT / "results/morning_risks.csv"   # 30 test mornings, every guest's score (scripts/eval_thresholds.py)
# The data ends in 2017, so the demo motel lives on a fixed day: the earliest of the 30 test mornings that
# flagged the average number of guests (7), with that morning's own sample, so the demo is a measured morning.
DAY = os.getenv("DEMO_DAY", "2017-02-01")
SEED = int(os.getenv("DEMO_SEED", "3"))
HISTORY_ROWS, ROOMS, DAYS_AHEAD = 3000, 20, 3   # a 20-room motel with about 3,000 past bookings
FLAG_LINE = 0.30   # owner's choice, 14 Oct; on 30 test mornings it flagged 3–13 guests a day, never none

# Fictional guests for the demo; the dataset has no names or contact details.
NAMES = ["Ana Silva", "Ben Carter", "Chloe Nguyen", "Daniel Okafor", "Elena Rossi", "Farid Haddad",
         "Grace Kim", "Hugo Martin", "Isla Murphy", "Jonas Berg", "Keira Walsh", "Liam O'Brien",
         "Maya Patel", "Noah Fischer", "Olivia Brown", "Pedro Costa", "Quinn Taylor", "Rosa Lopez",
         "Sam Wilson", "Tara Singh", "Umar Sheikh", "Vera Novak", "Will Chen", "Yara Haddad"]
FICTION_NUMBERS = ["006", "156", "157", "158", "159", "110", "313", "737", "808"]   # ACMA: 0491 570 xxx is for fiction
ACTION_STAGE = {"draft": "choose", "leave": "choose", "send": "review", "reject": "review"}


def contact(i: int, name: str) -> dict:
    if i % 2 == 0:
        return {"channel": "WhatsApp", "to": f"+61 491 570 {FICTION_NUMBERS[i // 2 % len(FICTION_NUMBERS)]}"}
    first, *rest = name.lower().replace("'", "").split()
    return {"channel": "email", "to": f"{first}.{rest[-1][0]}@example.com"}


def mock_send(booking: dict, text: str) -> dict:
    """Nothing leaves this computer: the message goes to the outbox file and the page says so."""
    sent = {**booking["contact"], "at": datetime.now().strftime("%H:%M"), "demo": True}
    OUTBOX.parent.mkdir(exist_ok=True)
    with OUTBOX.open("a") as f:
        f.write(json.dumps({"id": booking["id"], "guest": booking["guest"], "text": text, **sent}) + "\n")
    return sent


def app(db: Path = DB, **kw):
    db.parent.mkdir(exist_ok=True)
    return build(**{"sender": mock_send, **kw}, checkpointer=SqliteSaver(sqlite3.connect(db, check_same_thread=False)))


def morning(today: str, desk=None, seed: int = SEED) -> list[dict]:
    """Score the next few days' arrivals and start one graph run per booking. Runs once per day."""
    desk = desk or app()
    if guests(today, desk):
        return guests(today, desk)
    from tabpfn_client import TabPFNClassifier, set_access_token
    load_dotenv(ROOT / ".env")
    set_access_token(os.environ["TABPFN_API_KEY"])

    df = load()
    day = pd.Timestamp(today)
    history = df[df.arrival < day].sample(HISTORY_ROWS, random_state=seed)   # only outcomes known by today
    upcoming = df[(df.arrival >= day) & (df.arrival < day + pd.Timedelta(days=DAYS_AHEAD))
                  & (df.deposit_type == "No Deposit")].sample(ROOMS, random_state=seed)

    model = TabPFNClassifier()
    model.fit(history[FEATURES], history[TARGET])
    risks = model.predict_proba(upcoming[FEATURES])[:, 1]

    for i, ((idx, row), risk) in enumerate(zip(upcoming.iterrows(), risks)):
        name = NAMES[i % len(NAMES)]
        booking = {"id": f"{today}-{idx}", "guest": name, "contact": contact(i, name), "today": day.date(),
                   "arrival": row.arrival.date(), "lead_time": int(row.lead_time),
                   "stays_in_weekend_nights": int(row.stays_in_weekend_nights),
                   "stays_in_week_nights": int(row.stays_in_week_nights),
                   "adults": int(row.adults), "children": int(row.children),
                   "adr": float(row.adr), "reserved_room_type": str(row.reserved_room_type),
                   "channel": str(row.market_segment), "previous_cancellations": int(row.previous_cancellations),
                   "is_repeated_guest": bool(row.is_repeated_guest),
                   "special_requests": int(row.total_of_special_requests)}
        flagged = bool(risk >= FLAG_LINE)
        desk.invoke({"booking": booking, "risk": float(risk), "flagged": flagged,
                     "reasons": reasons(row, history) if flagged else []},
                    {"configurable": {"thread_id": booking["id"]}})
    return guests(today, desk)


def guests(today: str, desk=None) -> list[dict]:
    """Every booking of the day with where it stands, riskiest first."""
    desk = desk or app()
    # ponytail: scans every checkpoint; fine for one motel, index thread ids by day if it grows
    threads = {c.config["configurable"]["thread_id"] for c in desk.checkpointer.list(None)}
    return sorted((guest(t, desk) for t in threads if t.startswith(f"{today}-")), key=lambda g: -g["risk"])


def guest(thread: str, desk) -> dict:
    snap = desk.get_state({"configurable": {"thread_id": thread}})
    g = {"id": thread, "stage": snap.interrupts[0].value["stage"] if snap.interrupts else None, **snap.values}
    if "booking" in g:   # nights, total and channel for the page, worked out here rather than in the browser
        g.setdefault("facts", work_out_facts(g["booking"]))
        g["via"] = CHANNELS.get(g["booking"].get("channel"), g["booking"].get("channel"))
    return g


def act(thread: str, action: str, text: str | None = None, desk=None) -> dict:
    """Resume a paused run with the owner's choice. Refuses a choice the run isn't waiting for."""
    desk = desk or app()
    if ACTION_STAGE.get(action) is None or guest(thread, desk)["stage"] != ACTION_STAGE[action]:
        raise ValueError(f"{thread} is not waiting for {action!r}")
    answer = {"decision": "send", "text": text} if action == "send" and text else action
    desk.invoke(Command(resume=answer), {"configurable": {"thread_id": thread}})
    return guest(thread, desk)


def roi(line: float = FLAG_LINE) -> dict:
    """What this line did on the 30 test mornings: historical data, not a live motel."""
    r = pd.read_csv(RISKS)
    flagged, mornings = r[r.risk >= line], r.day.nunique()
    return {"mornings": mornings, "per_morning": round(len(flagged) / mornings, 1),
            "share_cancelled": round(float(flagged.cancelled.mean()), 2),
            "caught_per_morning": round(flagged.cancelled.sum() / mornings, 1),
            "caught": int(flagged.cancelled.sum()), "cancelled": int(r.cancelled.sum())}


if __name__ == "__main__":
    for g in morning(sys.argv[1] if len(sys.argv) > 1 else DAY):
        b = g["booking"]
        print(f"{b['guest']:<14} risk {g['risk']:.2f}  {'FLAGGED' if g['flagged'] else ''}")
