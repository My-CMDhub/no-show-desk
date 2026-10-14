"""Same 30 mornings as eval_mornings.py (same seeds), keeping every guest's risk score, so we can
compare 'flag everyone over X%' with 'flag the 5 riskiest'.

Run: .venv/bin/python scripts/eval_thresholds.py   (writes results/thresholds.md and morning_risks.csv)
"""
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.data import FEATURES, TARGET, load  # noqa: E402
from noshow.desk import DAYS_AHEAD, FLAG_TOP, HISTORY_ROWS, ROOMS  # noqa: E402

load_dotenv(ROOT / ".env")
from tabpfn_client import TabPFNClassifier, set_access_token  # noqa: E402
set_access_token(os.environ["TABPFN_API_KEY"])

OUT = ROOT / "results/morning_risks.csv"
if not OUT.exists():
    df = load()
    days = pd.date_range("2017-01-09", "2017-08-21", periods=30).normalize()
    rows = []
    for n, day in enumerate(days):
        history = df[df.arrival < day].sample(HISTORY_ROWS, random_state=n)
        upcoming = df[(df.arrival >= day) & (df.arrival < day + pd.Timedelta(days=DAYS_AHEAD))
                      & (df.deposit_type == "No Deposit")].sample(ROOMS, random_state=n)
        model = TabPFNClassifier()
        model.fit(history[FEATURES], history[TARGET])
        risk = model.predict_proba(upcoming[FEATURES])[:, 1]
        rows += [{"day": day.date(), "row": i, "risk": r, "cancelled": int(y)}
                 for i, r, y in zip(upcoming.index, risk, upcoming[TARGET])]
        print(day.date(), flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)

r = pd.read_csv(OUT)
mornings, total = r.day.nunique(), r.cancelled.sum()
r["rank"] = r.groupby("day").risk.rank(ascending=False, method="first")
rules = {f"Top {FLAG_TOP} each morning": r["rank"] <= FLAG_TOP}
rules |= {f"Risk {t:.0%} or more": r.risk >= t for t in (0.30, 0.45, 0.50)}
lines = []
for name, flag in rules.items():
    per_day = flag.groupby(r.day).sum()
    hit = r.cancelled[flag].sum()
    rand = (per_day * r.groupby("day").cancelled.mean()).sum()   # the same number per morning, picked at random
    lines.append(f"| {name} | {flag.sum()} | {per_day.min()}–{per_day.max()} | {(per_day == 0).sum()} | "
                 f"{hit} of {flag.sum()} ({hit / max(flag.sum(), 1):.0%}) | {hit} of {total} ({hit / total:.0%}) | {rand:.0f} |")
md = (f"# Threshold or top 5? Same {mornings} mornings, {len(r)} guests, {total} cancelled\n\n"
      "| Rule | Flagged | Per morning | Mornings with nobody flagged | Flagged who cancelled | Cancellations caught | Same number at random would catch |\n"
      "|---|---|---|---|---|---|---|\n" + "\n".join(lines) + "\n")
(ROOT / "results/thresholds.md").write_text(md)
print(md)
