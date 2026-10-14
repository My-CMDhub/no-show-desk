"""Before / after: does Gemma state the right dates and amounts when it must work them out itself,
versus when code hands it the facts? Same bookings, same model, same seeds; only the brief changes.

Run: .venv/bin/python scripts/eval_drafts.py [n_bookings] [repeats]
Writes results/drafts.jsonl (every draft) and results/drafts.md (the summary).
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.check import check_draft  # noqa: E402
from noshow.data import load, time_split  # noqa: E402
from noshow.desk import NAMES  # noqa: E402
from noshow.draft import MODEL, facts_brief, raw_brief, write_draft  # noqa: E402
from noshow.facts import work_out_facts  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
REPEATS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

_, test = time_split(load())
rows = test[test.deposit_type == "No Deposit"].sample(N, random_state=1)
bookings = [{"guest": NAMES[i % len(NAMES)], "arrival": r.arrival.date(), "adr": float(r.adr),
             "stays_in_weekend_nights": int(r.stays_in_weekend_nights),
             "stays_in_week_nights": int(r.stays_in_week_nights),
             "reserved_room_type": str(r.reserved_room_type)} for i, (_, r) in enumerate(rows.iterrows())]
bookings = [b for b in bookings if b["stays_in_weekend_nights"] + b["stays_in_week_nights"] > 0]

out = ROOT / "results/drafts.jsonl"
done = set()
if out.exists():   # resumable: a long run on a laptop can be stopped and picked up again
    done = {(d["i"], d["brief"], d["seed"]) for d in map(json.loads, out.open())}
with out.open("a") as f:
    for i, b in enumerate(bookings):
        facts = work_out_facts(b)
        for brief_name, brief in [("raw", raw_brief(b)), ("facts", facts_brief(facts))]:
            for seed in range(1, REPEATS + 1):
                if (i, brief_name, seed) in done:
                    continue
                t0 = time.time()
                text = write_draft(brief, seed=seed)
                problems = check_draft(text, facts)
                f.write(json.dumps({"i": i, "brief": brief_name, "seed": seed, "model": MODEL,
                                    "secs": round(time.time() - t0, 2), "draft": text,
                                    "problems": problems}) + "\n")
                f.flush()
                print(f"{i:>3} {brief_name:<5} seed {seed}: {len(problems)} problem(s)", flush=True)

drafts = [json.loads(line) for line in out.open()]
lines = ["# Before / after: facts worked out in code", "",
         f"{len(bookings)} no-deposit bookings from 2017 × {REPEATS} drafts each × 2 briefs. Model: {MODEL}.", "",
         "| Brief | Drafts | With a wrong or missing fact | Median seconds |", "|---|---|---|---|"]
for name, label in [("raw", "Raw booking record (model works it out)"), ("facts", "Facts worked out in code")]:
    ds = [d for d in drafts if d["brief"] == name]
    bad = sum(bool(d["problems"]) for d in ds)
    secs = sorted(d["secs"] for d in ds)[len(ds) // 2] if ds else 0
    lines.append(f"| {label} | {len(ds)} | {bad} ({bad / max(len(ds), 1):.0%}) | {secs:.1f} |")
    kinds = Counter(p.split()[0] for d in ds for p in d["problems"])
    lines.append(f"|  ↳ problem kinds | | {dict(kinds)} | |")
(ROOT / "results/drafts.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
