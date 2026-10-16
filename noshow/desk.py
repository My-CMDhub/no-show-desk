"""The morning run: score the demo motel's upcoming bookings in one TabPFN call, then start one graph
run per booking. Guests at or over the line pause, waiting for the owner to press Draft or Leave.

Run from the terminal: .venv/bin/python -m noshow.desk 2017-03-06
"""
import json
import os
from functools import lru_cache
import sqlite3
import sys
import threading
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from noshow.check import check_draft
from noshow.data import FEATURES, TARGET, load
from noshow.draft import SYSTEM, facts_brief
from noshow.graph import build
from noshow.facts import work_out_facts
from noshow.reasons import CHANNELS, reasons

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/desk.sqlite"
OUTBOX = ROOT / "data/outbox.jsonl"
RISKS = ROOT / "results/morning_risks.csv"   # 30 test mornings, every guest's score (scripts/eval_thresholds.py)
SNAPSHOT = ROOT / "results/demo_snapshot.json"   # the demo morning, replays and recorded drafts (scripts/snapshot.py)
# Hosted: no dataset, no TabPFN key, no Ollama. Everything comes from the snapshot, each visitor gets their own
# copy of the demo morning, and drafts are written in the visitor's browser.
HOSTED = os.getenv("HOSTED") == "1"
# The data ends in 2017, so the demo motel lives on a fixed day: the earliest of the 30 test mornings that
# flagged the average number of guests (7), with that morning's own sample, so the demo is a measured morning.
DAY = os.getenv("DEMO_DAY", "2017-02-01")
SEED = int(os.getenv("DEMO_SEED", "3"))
HISTORY_ROWS, ROOMS, DAYS_AHEAD = 3000, 20, 3   # a 20-room motel with about 3,000 past bookings
LATER, LATER_DAYS = 30, 14   # bookings further out, listed in the bookings view, never flagged yet
FLAG_LINE = 0.30   # owner's choice, 14 Oct; on 30 test mornings it flagged 3–13 guests a day, never none

# Fictional guests for the demo; the dataset has no names or contact details.
NAMES = ["Ana Silva", "Ben Carter", "Chloe Nguyen", "Daniel Okafor", "Elena Rossi", "Farid Haddad",
         "Grace Kim", "Hugo Martin", "Isla Murphy", "Jonas Berg", "Keira Walsh", "Liam O'Brien",
         "Maya Patel", "Noah Fischer", "Olivia Brown", "Pedro Costa", "Quinn Taylor", "Rosa Lopez",
         "Sam Wilson", "Tara Singh", "Umar Sheikh", "Vera Novak", "Will Chen", "Yara Haddad",
         "Zoe Adams", "Arjun Rao", "Bea Lindqvist", "Caleb Wright", "Dana Ivanova", "Emil Strand", "Fatima Ali",
         "George Papas", "Hana Sato", "Ivan Petrov", "Julia Marino", "Kofi Mensah", "Lena Vogel", "Marco Bianchi",
         "Nadia Karim", "Oscar Lund", "Priya Nair", "Raf Torres", "Sofia Lima", "Theo Grant", "Uma Das",
         "Victor Hugo Ruiz", "Wren Clarke", "Ximena Soto", "Yusuf Demir", "Zara Hale"]
FICTION_NUMBERS = ["006", "156", "157", "158", "159", "110", "313", "737", "808"]   # ACMA: 0491 570 xxx is for fiction
ACTION_STAGE = {"draft": "choose", "leave": "choose", "send": "review", "reject": "review"}
_LOCKS: dict[str, threading.Lock] = {}   # one per guest: two taps, tabs or phones can't both act on one run


class NeedsOwner(Exception):
    """The owner's own text has a problem; they must fix it or say send anyway."""
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def contact(i: int, name: str) -> dict:
    if i % 6 == 0 and i // 6 < len(FICTION_NUMBERS):   # only as many WhatsApp guests as there are fiction numbers
        return {"channel": "WhatsApp", "to": f"+61 491 570 {FICTION_NUMBERS[i // 6]}"}
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
    saver = SqliteSaver(sqlite3.connect(db, check_same_thread=False))
    saver.setup()   # tables now, not at the first save: a fresh host lists guests before anything is saved
    return build(**{"sender": mock_send, **kw}, checkpointer=saver)


@lru_cache
def snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text())


def tid(visitor: str, booking_id: str) -> str:
    """Graph run id: the booking id, behind the visitor's id when hosted (one desk per visitor)."""
    return f"{visitor}~{booking_id}" if visitor else booking_id


def morning(today: str, desk=None, seed: int = SEED, visitor: str = "") -> list[dict]:
    """Score the next few days' arrivals and start one graph run per booking. Runs once per day."""
    desk = desk or app()
    if guests(today, desk, visitor):
        return guests(today, desk, visitor)
    if HOSTED:   # the demo morning as scored on the owner's Mac (same bookings, same scores)
        for st in snapshot()["morning"]:
            b = {**st["booking"], "today": date.fromisoformat(st["booking"]["today"]),
                 "arrival": date.fromisoformat(st["booking"]["arrival"])}
            desk.invoke({**st, "booking": b}, {"configurable": {"thread_id": tid(visitor, b["id"])}})
        return guests(today, desk, visitor)
    from tabpfn_client import TabPFNClassifier, set_access_token
    load_dotenv(ROOT / ".env")
    set_access_token(os.environ["TABPFN_API_KEY"])

    df = load()
    day = pd.Timestamp(today)
    history = df[df.arrival < day].sample(HISTORY_ROWS, random_state=seed)   # only outcomes known by today
    no_deposit = df[df.deposit_type == "No Deposit"]
    upcoming = no_deposit[(no_deposit.arrival >= day) & (no_deposit.arrival < day + pd.Timedelta(days=DAYS_AHEAD))
                          ].sample(ROOMS, random_state=seed)   # the measured morning (scripts/eval_thresholds.py)
    later = no_deposit[(no_deposit.arrival >= day + pd.Timedelta(days=DAYS_AHEAD))
                       & (no_deposit.arrival < day + pd.Timedelta(days=LATER_DAYS))
                       & (no_deposit.adr >= 20)].sample(LATER, random_state=seed)   # no complimentary $0 stays
    both = pd.concat([upcoming, later])

    model = TabPFNClassifier()
    model.fit(history[FEATURES], history[TARGET])
    risks = model.predict_proba(both[FEATURES])[:, 1]   # each booking is scored against history alone

    for i, ((idx, row), risk) in enumerate(zip(both.iterrows(), risks)):
        name = NAMES[i % len(NAMES)]
        booking = {"id": f"{today}-{idx}", "guest": name, "contact": contact(i, name), "today": day.date(),
                   "arrival": row.arrival.date(), "lead_time": int(row.lead_time),
                   "stays_in_weekend_nights": int(row.stays_in_weekend_nights),
                   "stays_in_week_nights": int(row.stays_in_week_nights),
                   "adults": int(row.adults), "children": int(row.children),
                   "adr": float(row.adr), "reserved_room_type": str(row.reserved_room_type),
                   "channel": str(row.market_segment), "previous_cancellations": int(row.previous_cancellations),
                   "is_repeated_guest": bool(row.is_repeated_guest),
                   "special_requests": int(row.total_of_special_requests), "due": i < ROOMS}
        flagged = bool(booking["due"] and risk >= FLAG_LINE)   # later bookings are listed, not messaged yet
        desk.invoke({"booking": booking, "risk": float(risk), "flagged": flagged,
                     "reasons": reasons(row, history) if risk >= FLAG_LINE else []},
                    {"configurable": {"thread_id": tid(visitor, booking["id"])}})
    return guests(today, desk)


def guests(today: str, desk=None, visitor: str = "") -> list[dict]:
    """Every booking of the day with where it stands, riskiest first."""
    desk = desk or app()
    start = tid(visitor, f"{today}-")
    threads = [t for (t,) in desk.checkpointer.conn.execute(   # thread ids only: cheap with many hosted visitors
        "SELECT DISTINCT thread_id FROM checkpoints WHERE substr(thread_id, 1, ?) = ?", (len(start), start))]
    return sorted((guest(t, desk) for t in threads), key=lambda g: -g["risk"])


def guest(thread: str, desk) -> dict:
    snap = desk.get_state({"configurable": {"thread_id": thread}})
    g = {"id": thread, "stage": snap.interrupts[0].value["stage"] if snap.interrupts else None, **snap.values}
    if "booking" in g:   # nights, total and channel for the page, worked out here rather than in the browser
        g.setdefault("facts", work_out_facts(g["booking"]))
        g["via"] = CHANNELS.get(g["booking"].get("channel"), g["booking"].get("channel"))
    return g


def brief(thread: str, desk=None) -> dict:
    """What the browser's Gemma needs to write this guest's message, and the draft recorded on the owner's Mac."""
    g = guest(thread, desk or app())
    rec = snapshot().get("recorded", {}).get(g["booking"]["id"]) if SNAPSHOT.exists() else None
    return {"system": SYSTEM, "brief": facts_brief(g["facts"]), "recorded": rec}


def act(thread: str, action: str, text: str | None = None, desk=None, anyway: bool = False, by: str | None = None) -> dict:
    """Resume a paused run with the owner's choice. Refuses a choice the run isn't waiting for, and checks
    the owner's own wording the same way the model's draft was checked. Draft can bring its own text, written
    in the owner's browser (by="browser") or the one recorded earlier on the owner's Mac (by="recorded")."""
    desk = desk or app()
    with _LOCKS.setdefault(thread, threading.Lock()):
        g = guest(thread, desk)
        if ACTION_STAGE.get(action) is None or g["stage"] != ACTION_STAGE[action]:
            raise ValueError(f"{thread} is not waiting for {action!r}")
        if action == "send" and text is not None:
            text = text.strip()
            if not text:
                raise NeedsOwner(["the message is empty"])
            problems = check_draft(text, g["facts"])
            if problems and not anyway:
                raise NeedsOwner(problems)
        answer = {"decision": "send", "text": text} if action == "send" and text else action
        if action == "draft" and by == "recorded":   # the server's own copy, never text sent by the page
            rec = brief(thread, desk)["recorded"]
            if not rec:
                raise ValueError(f"{thread} has no recorded draft")
            answer = {"decision": "draft", "text": rec["text"], "by": "recorded"}
        elif action == "draft" and text:
            answer = {"decision": "draft", "text": text.strip(), "by": "browser"}
        desk.invoke(Command(resume=answer), {"configurable": {"thread_id": thread}})
        return guest(thread, desk)


def shared_reasons(day_guests: list[dict]) -> list[dict]:
    """Reasons every flagged guest has: said once for the morning, not repeated on each guest."""
    flagged = [g for g in day_guests if g.get("flagged")]
    if len(flagged) < 2:
        return []
    return [r for r in flagged[0]["reasons"]
            if all(r["label"] in {x["label"] for x in g["reasons"]} for g in flagged[1:])]


def at_risk(day_guests: list[dict]) -> dict:
    flagged = [g for g in day_guests if g.get("flagged")]
    return {"guests": len(flagged), "total": f"${sum(g['facts']['amount'] for g in flagged):,.2f}"}


def roi() -> dict:
    return snapshot()["roi"] if HOSTED else live_roi()


@lru_cache
def live_roi(line: float = FLAG_LINE) -> dict:
    """What this line did on the 30 test mornings: historical data, not a live motel."""
    r = pd.read_csv(RISKS)
    df = load()
    r["total"] = r.row.map(df.adr * (df.stays_in_weekend_nights + df.stays_in_week_nights))   # whole-stay totals
    flagged, mornings = r[r.risk >= line], r.day.nunique()
    return {"mornings": mornings, "per_morning": round(len(flagged) / mornings, 1),
            "share_cancelled": round(float(flagged.cancelled.mean()), 2),
            "caught_per_morning": round(flagged.cancelled.sum() / mornings, 1),
            "caught": int(flagged.cancelled.sum()), "cancelled": int(r.cancelled.sum()),
            "caught_value_per_morning": f"${flagged.total[flagged.cancelled == 1].sum() / mornings:,.0f}",
            "random_caught_per_morning": round(sum((d.risk >= line).sum() * d.cancelled.mean()
                                                   for _, d in r.groupby("day")) / mornings, 1)}


def replay(year: str) -> dict:
    return snapshot()["replay"][year] if HOSTED else live_replay(year)


@lru_cache
def live_replay(year: str) -> dict:
    """The 30 stored mornings of a year with what really happened, for the page to replay. Scores were made
    from bookings before each morning only (scripts/eval_thresholds.py); the page hides the outcomes until reveal.
    Same sample and order as morning(), so the demo morning's guests keep their names and ids."""
    r = pd.read_csv(RISKS.with_stem(RISKS.stem + ("" if year == "2017" else f"_{year}")))
    df = load()
    mornings = []
    for d, m in r.groupby("day", sort=True):
        rows = df.loc[m.row]
        nights = (rows.stays_in_weekend_nights + rows.stays_in_week_nights).to_numpy()
        # risk stays unrounded: rounding to 4 places lifts a 29.996% guest over the 30% line
        mornings.append({"day": d, "guests": [
            {"id": f"{d}-{x.row}", "row": int(x.row), "name": NAMES[i % len(NAMES)], "risk": float(x.risk),
             "cancelled": int(x.cancelled), "arrival": str(a.date()), "nights": int(n), "total": round(float(adr * n), 2)}
            for i, (x, a, n, adr) in enumerate(zip(m.itertuples(), rows.arrival, nights, rows.adr))]})
    return {"year": year, "line": FLAG_LINE, "mornings": mornings}


if __name__ == "__main__":
    for g in morning(sys.argv[1] if len(sys.argv) > 1 else DAY):
        b = g["booking"]
        print(f"{b['guest']:<14} risk {g['risk']:.2f}  {'FLAGGED' if g['flagged'] else ''}")
