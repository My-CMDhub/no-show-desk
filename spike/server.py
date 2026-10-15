"""Spike: can Gemma 4 E2B running in the browser (LiteRT-LM, WebGPU) write the reconfirm message as well as
Ollama did? Same bookings, same system prompt, same brief, same checker; only where the model runs changes.

Run: .venv/bin/python -m spike.server   then open http://localhost:8001 (stop Ollama's model first: 8 GB Mac)
Full run: SPIKE_FULL=1 drafts all 50 bookings twice (seeds 1 and 2), like results/drafts_reconfirm.md.
Model file: data/models/gemma-4-E2B-it-web.litertlm (2.0 GB, git-ignored; the page fetches it from here).
"""
import json
import os
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from noshow.check import check_draft
from noshow.data import load, time_split
from noshow.desk import NAMES
from noshow.draft import SYSTEM, facts_brief
from noshow.facts import work_out_facts

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data/models/gemma-4-E2B-it-web.litertlm"
FULL = os.getenv("SPIKE_FULL") == "1"
OUT = ROOT / ("results/drafts_browser.jsonl" if FULL else "results/drafts_browser_spike.jsonl")
N, SEEDS = (50, [1, 2]) if FULL else (20, [1])

# The same sample as scripts/eval_drafts.py with a tag (random_state=1, seen 0–2 days before arrival).
_, test = time_split(load())
rows = test[test.deposit_type == "No Deposit"].sample(50, random_state=1)
BOOKINGS = [{"guest": NAMES[i % 24],   # the 24 names the Ollama runs used, so the briefs match word for word
             "arrival": r.arrival.date(), "adr": float(r.adr),
             "stays_in_weekend_nights": int(r.stays_in_weekend_nights),
             "stays_in_week_nights": int(r.stays_in_week_nights),
             "reserved_room_type": str(r.reserved_room_type), "today": r.arrival.date() - timedelta(days=i % 3)}
            for i, (_, r) in enumerate(rows.iterrows())]
BOOKINGS = [b for b in BOOKINGS if b["stays_in_weekend_nights"] + b["stays_in_week_nights"] > 0][:N]

app = FastAPI()


class Draft(BaseModel):
    i: int
    seed: int
    draft: str
    secs: float


@app.get("/")
def page():
    return FileResponse(Path(__file__).with_name("page.html"), headers={"Cache-Control": "no-cache"})


@app.get("/model")
def model():
    if not MODEL.exists():
        raise HTTPException(404, "model file not downloaded yet")
    return FileResponse(MODEL, media_type="application/octet-stream")


@app.get("/briefs")
def briefs():
    return {"system": SYSTEM, "seeds": SEEDS, "briefs": [{"i": i, "brief": facts_brief(work_out_facts(b))} for i, b in enumerate(BOOKINGS)]}


@app.post("/check")
def check(d: Draft):
    if not 0 <= d.i < len(BOOKINGS):
        raise HTTPException(404, "no such booking")
    problems = check_draft(d.draft, work_out_facts(BOOKINGS[d.i]))
    with OUT.open("a") as f:
        f.write(json.dumps({**d.model_dump(), "brief": "facts", "model": "gemma-4-E2B-it-web (LiteRT-LM, browser)",
                            "problems": problems}) + "\n")
    return {"problems": problems}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
