"""The hosted demo's data, saved once on the owner's Mac so the host needs no dataset, no TabPFN key and no
Ollama: the demo morning as TabPFN scored it, both replay years, the line's 30-morning numbers, and one recorded
draft per flagged guest (Gemma 4 E2B through Ollama, checked like the desk checks, read by hand).

Run: .venv/bin/python scripts/snapshot.py   (needs data/desk.sqlite with the demo morning; Ollama for new drafts)
Recorded drafts already in results/demo_snapshot.json are kept, so re-running doesn't rewrite them.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow import desk  # noqa: E402
from noshow.check import check_draft  # noqa: E402
from noshow.draft import MODEL, facts_brief, write_draft  # noqa: E402

old = json.loads(desk.SNAPSHOT.read_text()) if desk.SNAPSHOT.exists() else {}
gs = desk.guests(desk.DAY, desk.app())
assert len(gs) == desk.ROOMS + desk.LATER, "run the demo morning first (the page's button, or python -m noshow.desk)"

recorded = old.get("recorded", {})
for g in gs:
    bid = g["booking"]["id"]
    if not g["flagged"] or bid in recorded:
        continue
    for attempt in (1, 2):   # as on the desk: one redraft if the check finds a wrong fact
        text = write_draft(facts_brief(g["facts"]), seed=attempt)
        problems = check_draft(text, g["facts"])
        if not problems:
            break
    recorded[bid] = {"text": text, "problems": problems, "attempts": attempt, "model": f"Gemma 4 E2B ({MODEL}, Ollama)"}
    print(f"{g['booking']['guest']}: {problems or 'ok'}\n  {text}\n", flush=True)

snap = {"day": desk.DAY, "line": desk.FLAG_LINE,
        "morning": [{k: g[k] for k in ("booking", "risk", "flagged", "reasons")} for g in gs],
        "roi": desk.live_roi(), "replay": {y: desk.live_replay(y) for y in ("2017", "2016")}, "recorded": recorded}
desk.SNAPSHOT.write_text(json.dumps(snap, default=str, indent=1) + "\n")
print(f"wrote {desk.SNAPSHOT.relative_to(ROOT)}: {len(snap['morning'])} bookings, {len(recorded)} recorded drafts")
