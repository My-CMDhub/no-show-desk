"""Does TabPFN run on the owner's own computer, and does it agree with the API? TabPFN's v2 weights (the commercially
licensed ones) run locally on the 30 test mornings of eval_thresholds.py: the same 600 guests, same histories and seeds.
Nothing settled changes: the API scores in morning_risks.csv stay the desk's numbers; this is a separate check.

Run (its own environment, so the app's dependencies stay as they are):
  python3.12 -m venv .venv-tabpfn && .venv-tabpfn/bin/pip install tabpfn pandas scikit-learn tabulate
  .venv-tabpfn/bin/python scripts/eval_local_v2.py      (writes results/local_v2.md and results/local_v2_risks.csv)
"""
import sys
import time
from pathlib import Path

import pandas as pd
import torch
from sklearn.metrics import roc_auc_score
from tabpfn import TabPFNClassifier
from tabpfn.constants import ModelVersion

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ast  # noqa: E402

from noshow.data import FEATURES, TARGET, load  # noqa: E402


def desk_constants(*names):
    """The desk's own module-level constants, read from its source: importing desk.py would pull in LangGraph,
    which this environment deliberately leaves out."""
    found = {}
    for node in ast.parse((ROOT / "noshow/desk.py").read_text()).body:
        if isinstance(node, ast.Assign):
            targets = node.targets[0].elts if isinstance(node.targets[0], ast.Tuple) else node.targets
            values = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
            for t, v in zip(targets, values):
                if isinstance(t, ast.Name) and t.id in names:
                    found[t.id] = ast.literal_eval(v)
    return [found[n] for n in names]


DAYS_AHEAD, HISTORY_ROWS, ROOMS, FLAG_LINE = desk_constants("DAYS_AHEAD", "HISTORY_ROWS", "ROOMS", "FLAG_LINE")
assert (DAYS_AHEAD, HISTORY_ROWS, ROOMS, FLAG_LINE) == (3, 3000, 20, 0.30), "the desk's settings moved; check the protocol"
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
df = load()
api = pd.read_csv(ROOT / "results/morning_risks.csv")
days = pd.date_range("2017-01-09", "2017-08-21", periods=30).normalize()
rows, seconds = [], []
for n, day in enumerate(days):   # the same samples as eval_thresholds.py and eval_logistic.py
    history = df[df.arrival < day].sample(HISTORY_ROWS, random_state=n)
    upcoming = df[(df.arrival >= day) & (df.arrival < day + pd.Timedelta(days=DAYS_AHEAD))
                  & (df.deposit_type == "No Deposit")].sample(ROOMS, random_state=n)
    t = time.perf_counter()
    model = TabPFNClassifier.create_default_for_version(ModelVersion.V2, device=DEVICE, random_state=0)
    p = model.fit(history[FEATURES], history[TARGET]).predict_proba(upcoming[FEATURES])[:, 1]
    seconds.append(time.perf_counter() - t)
    rows += [{"day": str(day.date()), "row": i, "local": s} for i, s in zip(upcoming.index, p)]
    print(f"{day.date()}  {seconds[-1]:.1f} s", flush=True)

m = api.merge(pd.DataFrame(rows), on=["day", "row"])
assert len(m) == len(api) == 600, "the mornings must be the same 600 guests"
m.to_csv(ROOT / "results/local_v2_risks.csv", index=False)
budget = (m.risk >= FLAG_LINE).groupby(m.day).sum()
at_line = lambda col: (int(((m[col] >= FLAG_LINE) & (m.cancelled == 1)).sum()), int((m[col] >= FLAG_LINE).sum()))
same_budget = lambda col: int(sum(g.sort_values(col, ascending=False).head(budget[d]).cancelled.sum() for d, g in m.groupby("day")))
(api_c, api_n), (loc_c, loc_n) = at_line("risk"), at_line("local")
demo = m[m.day == "2017-02-01"]
flag_api, flag_loc = set(demo.row[demo.risk >= FLAG_LINE]), set(demo.row[demo.local >= FLAG_LINE])

out = ["# TabPFN v2 run on the owner's computer, against the API scores the desk uses\n",
       f"Local: `tabpfn` with ModelVersion.V2 weights (Prior Labs License: Apache 2.0 + attribution, commercial use allowed), "
       f"on {DEVICE.upper()} of an 8 GB M2 Mac. API: the scores in `morning_risks.csv` (tabpfn-client defaults). "
       "Same 30 mornings of 2017, same 600 guests, same 3,000-booking histories.\n",
       "| | API (the desk's numbers) | v2 on this Mac |", "|---|---|---|",
       f"| Flagged at the {FLAG_LINE:.0%} line | {api_n} | {loc_n} |",
       f"| Cancellations caught at that line, of 172 | {api_c} | {loc_c} |",
       f"| Caught with the same message budget as the desk ({int(budget.sum())}) | {same_budget('risk')} | {same_budget('local')} |",
       f"| ROC-AUC over the 600 guests | {roc_auc_score(m.cancelled, m.risk):.3f} | {roc_auc_score(m.cancelled, m.local):.3f} |",
       f"\nScore agreement: Pearson {m.risk.corr(m.local):.3f}, Spearman {m.risk.corr(m.local, method='spearman'):.3f}; "
       f"same side of the {FLAG_LINE:.0%} line for {int(((m.risk >= FLAG_LINE) == (m.local >= FLAG_LINE)).sum())} of 600 guests.",
       f"\nDemo morning (2017-02-01): API flags {len(flag_api)}, v2 flags {len(flag_loc)}, both flag {len(flag_api & flag_loc)}.",
       f"\nTime per morning (fit on 3,000 bookings + score 20): median {pd.Series(seconds).median():.1f} s, "
       f"max {max(seconds):.1f} s, total {sum(seconds) / 60:.1f} min (first morning includes loading the weights)."]
(ROOT / "results/local_v2.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
