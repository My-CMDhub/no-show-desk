"""Thirty mornings at a 20-room motel in 2017: of the 5 guests flagged each morning, how many
really cancelled, compared with messaging 5 guests at random?

Run: .venv/bin/python scripts/eval_mornings.py   (writes results/mornings.md and .csv)
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.data import FEATURES, TARGET, load  # noqa: E402
from noshow.desk import DAYS_AHEAD, HISTORY_ROWS, ROOMS  # noqa: E402
FLAG_TOP = 5   # the earlier rule, kept for comparison: message the 5 riskiest each morning

load_dotenv(ROOT / ".env")
from tabpfn_client import TabPFNClassifier, set_access_token  # noqa: E402
set_access_token(os.environ["TABPFN_API_KEY"])

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
    y = upcoming[TARGET].to_numpy()
    top = np.argsort(risk)[::-1][:FLAG_TOP]
    rows.append({"day": day.date(), "cancelled": int(y.sum()), "flagged_cancelled": int(y[top].sum()),
                 "random_expected": FLAG_TOP * y.mean()})
    print(rows[-1], flush=True)

r = pd.DataFrame(rows)
r.to_csv(ROOT / "results/mornings.csv", index=False)
flag_hits, rand_hits, total = r.flagged_cancelled.sum(), r.random_expected.sum(), r.cancelled.sum()
md = ("# Thirty mornings at a 20-room motel (2017)\n\n"
      f"Each morning: {ROOMS} upcoming no-deposit bookings, TabPFN learns from {HISTORY_ROWS:,} earlier bookings, "
      f"the {FLAG_TOP} riskiest are flagged.\n\n"
      f"- Flagged guests who really cancelled: **{flag_hits} of {FLAG_TOP * len(r)}** "
      f"({flag_hits / (FLAG_TOP * len(r)):.0%})\n"
      f"- Five guests picked at random would have caught about **{rand_hits:.0f}** ({rand_hits / (FLAG_TOP * len(r)):.0%})\n"
      f"- Cancellations caught by the flags: **{flag_hits} of {total}** ({flag_hits / total:.0%}), "
      f"while messaging a quarter of guests\n"
      f"- Mornings where the flags caught more than chance: {(r.flagged_cancelled > r.random_expected).sum()} of {len(r)}\n")
(ROOT / "results/mornings.md").write_text(md)
print(md)
