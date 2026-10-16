"""Would a plain logistic regression do as well as TabPFN? Two checks, both local (no API calls):

1. The small-history test of eval_small_history.py: same 5,000 no-deposit 2017 arrivals, same 3 histories per size.
2. The 30 test mornings of eval_thresholds.py: each morning's own 3,000-booking history and 20 arrivals (same seeds),
   messaging as many guests per morning as the desk's 30% line did, ranked by the regression instead.

Run: .venv/bin/python scripts/eval_logistic.py   (writes results/logistic.md)
"""
import sys
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.data import CATEGORICAL, FEATURES, NUMERIC, TARGET, load, time_split  # noqa: E402
from noshow.desk import DAYS_AHEAD, HISTORY_ROWS, ROOMS  # noqa: E402


def logistic():
    prep = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL), ("num", StandardScaler(), NUMERIC)])
    return make_pipeline(prep, LogisticRegression(max_iter=5000))


df = load()

# 1. small histories, against the stored TabPFN and gradient boosting scores
train_all, test_all = time_split(df)
test = test_all[test_all.deposit_type == "No Deposit"].sample(5000, random_state=0)
rows = []
for n in [300, 1000, 3000]:
    for seed in [1, 2, 3]:
        hist = train_all.sample(n, random_state=seed)
        auc = roc_auc_score(test[TARGET], logistic().fit(hist[FEATURES], hist[TARGET]).predict_proba(test[FEATURES])[:, 1])
        rows.append({"history": n, "seed": seed, "model": "Logistic regression", "auc": auc})
small = pd.concat([pd.read_csv(ROOT / "results/small_history.csv"), pd.DataFrame(rows)])
table1 = small.groupby(["history", "model"]).auc.mean().unstack("model").round(3)
wide = small.pivot_table(index=["history", "seed"], columns="model", values="auc")
ahead = (wide["TabPFN"] > wide["Logistic regression"]).groupby("history").sum()

# 2. the 30 test mornings, same message budget as the desk's 30% line
r = pd.read_csv(ROOT / "results/morning_risks.csv")
days = pd.date_range("2017-01-09", "2017-08-21", periods=30).normalize()
lr_scores = []
for n, day in enumerate(days):   # the same samples as eval_thresholds.py
    history = df[df.arrival < day].sample(HISTORY_ROWS, random_state=n)
    upcoming = df[(df.arrival >= day) & (df.arrival < day + pd.Timedelta(days=DAYS_AHEAD))
                  & (df.deposit_type == "No Deposit")].sample(ROOMS, random_state=n)
    p = logistic().fit(history[FEATURES], history[TARGET]).predict_proba(upcoming[FEATURES])[:, 1]
    lr_scores += [{"day": str(day.date()), "row": i, "lr": s} for i, s in zip(upcoming.index, p)]
m = r.merge(pd.DataFrame(lr_scores), on=["day", "row"])
assert len(m) == len(r) == 600, "the mornings must be the same 600 guests"
budget = (m.risk >= 0.30).groupby(m.day).sum()
caught = lambda col: int(sum(g.sort_values(col, ascending=False).head(budget[d]).cancelled.sum() for d, g in m.groupby("day")))
auc_tab, auc_lr = roc_auc_score(m.cancelled, m.risk), roc_auc_score(m.cancelled, m.lr)

out = ["# TabPFN against a plain logistic regression\n",
       "Logistic regression: one-hot categories, scaled numbers, scikit-learn defaults otherwise. Fitted here, no API.\n",
       "## 1. Motel-sized histories (ROC-AUC, mean of 3 histories; same test as small_history.md)\n",
       table1.to_markdown(), "\nTabPFN ahead of logistic regression (of 3): "
       + ", ".join(f"{k:,} bookings: {v}" for k, v in ahead.items()) + "\n",
       "## 2. The 30 test mornings of 2017 (600 guests, 172 cancelled)\n",
       f"Each model messages the same number of guests per morning as the desk's 30% line ({int(budget.sum())} in all).\n",
       "| Model | Cancellations caught | ROC-AUC over the 600 guests |", "|---|---|---|",
       f"| TabPFN | {caught('risk')} of 172 | {auc_tab:.3f} |", f"| Logistic regression | {caught('lr')} of 172 | {auc_lr:.3f} |"]
(ROOT / "results/logistic.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
