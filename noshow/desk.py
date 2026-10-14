"""The morning run: score the demo motel's upcoming bookings in one TabPFN call,
then run the graph once per booking. Flagged bookings pause, waiting for the owner.

Run from the terminal: .venv/bin/python -m noshow.desk 2017-03-06
"""
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

from noshow.data import FEATURES, TARGET, load
from noshow.graph import build

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/desk.sqlite"
HISTORY_ROWS, ROOMS, DAYS_AHEAD = 3000, 20, 3   # a 20-room motel with about 3,000 past bookings
FLAG_TOP = 5   # the owner messages the 5 riskiest guests each morning, not everyone over a fixed line

# Fictional guests for the demo; the dataset has no names.
NAMES = ["Ana Silva", "Ben Carter", "Chloe Nguyen", "Daniel Okafor", "Elena Rossi", "Farid Haddad",
         "Grace Kim", "Hugo Martin", "Isla Murphy", "Jonas Berg", "Keira Walsh", "Liam O'Brien",
         "Maya Patel", "Noah Fischer", "Olivia Brown", "Pedro Costa", "Quinn Taylor", "Rosa Lopez",
         "Sam Wilson", "Tara Singh", "Umar Sheikh", "Vera Novak", "Will Chen", "Yara Haddad"]


def app():
    DB.parent.mkdir(exist_ok=True)
    return build(checkpointer=SqliteSaver(sqlite3.connect(DB, check_same_thread=False)))


def morning(today: str, seed: int = 0) -> list[dict]:
    """Score the next few days' arrivals and start one graph run per booking."""
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

    line = sorted(risks, reverse=True)[FLAG_TOP - 1]
    desk, results = app(), []
    for i, ((idx, row), risk) in enumerate(zip(upcoming.iterrows(), risks)):
        booking = {"id": f"{today}-{idx}", "guest": NAMES[i % len(NAMES)], "arrival": row.arrival.date(),
                   "stays_in_weekend_nights": int(row.stays_in_weekend_nights),
                   "stays_in_week_nights": int(row.stays_in_week_nights),
                   "adr": float(row.adr), "reserved_room_type": str(row.reserved_room_type)}
        cfg = {"configurable": {"thread_id": booking["id"]}}
        out = desk.invoke({"booking": booking, "risk": float(risk), "flagged": bool(risk >= line)}, cfg)
        results.append({"id": booking["id"], "guest": booking["guest"], "risk": float(risk),
                        "paused": "__interrupt__" in out, "cancelled": bool(row[TARGET])})
    return results


def pending(desk=None) -> list[dict]:
    """Every run waiting for the owner, with what the pause carried."""
    desk = desk or app()
    waiting = []
    for thread in {c.config["configurable"]["thread_id"] for c in desk.checkpointer.list(None)}:
        snap = desk.get_state({"configurable": {"thread_id": thread}})
        if snap.interrupts:
            waiting.append({"id": thread, **snap.interrupts[0].value})
    return sorted(waiting, key=lambda w: -w["risk"])


if __name__ == "__main__":
    for r in morning(sys.argv[1] if len(sys.argv) > 1 else "2017-03-06"):
        print(f"{r['guest']:<14} risk {r['risk']:.2f}  {'DRAFT WAITING' if r['paused'] else '-':<13}"
              f" (really cancelled: {r['cancelled']})")
