"""Is TabPFN worth it over a rule an owner could apply by hand? And do its percentages mean what they say?
Uses the stored scores of the 30 test mornings (results/morning_risks.csv); no API calls.

Run: .venv/bin/python scripts/eval_baselines.py   (writes results/baselines.md)
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.data import load  # noqa: E402

LINE = 0.30
df = load()
r = pd.read_csv(ROOT / "results/morning_risks.csv")
r = r.join(df[["agent", "lead_time", "market_segment", "total_of_special_requests"]], on="row")
budget = (r.risk >= LINE).groupby(r.day).sum()   # each rule messages as many guests per morning as the desk


def caught(score) -> int:
    ranked = r.assign(s=score).sort_values(["day", "s"], ascending=[True, False]).groupby("day", sort=False)
    return int(sum(g.head(budget[d]).cancelled.sum() for d, g in ranked))


rules = {   # tie-breaks by lead time, the strongest single column a person would look at
    "TabPFN, 30% line (the desk)": r.risk,
    "Online travel agent first, then longest lead time": (r.market_segment.astype(str) == "Online TA") * 1e4 + r.lead_time,
    "Travel agent #9 first, then longest lead time": (r.agent.astype(str) == "9") * 1e4 + r.lead_time,
    "No special requests first, then longest lead time": (r.total_of_special_requests == 0) * 1e4 + r.lead_time,
    "Longest lead time first": r.lead_time.astype(float),
}
total, n = int(r.cancelled.sum()), int(budget.sum())
lines = [f"# TabPFN against rules an owner could apply by hand\n",
         f"Same 30 test mornings, 600 guests, {total} cancelled. Every rule messages the same number of guests each "
         f"morning as the desk's 30% line ({n} in all), ranked by the rule.\n",
         "| Rule | Cancellations caught |", "|---|---|"]
lines += [f"| {k} | {caught(s)} of {total} |" for k, s in rules.items()]

r["band"] = pd.cut(r.risk, [0, .1, .2, .3, .4, .5, .6, 1.0])
cal = r.groupby("band", observed=True).agg(guests=("risk", "size"), said=("risk", "mean"), did=("cancelled", "mean"))
lines += ["\n## Do the percentages mean what they say?\n",
          "Guests grouped by the risk TabPFN gave them, against how many of each group really cancelled.\n",
          "| Risk band | Guests | Average risk given | Really cancelled |", "|---|---|---|---|"]
lines += [f"| {b.left:.0%}–{b.right:.0%} | {int(row.guests)} | {row.said:.0%} | {row.did:.0%} |" for b, row in cal.iterrows()]
(ROOT / "results/baselines.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
