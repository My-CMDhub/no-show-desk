"""Which model ranks risky bookings best? Baselines vs TabPFN on a time split.

Run: .venv/bin/python scripts/eval_risk.py  (writes results/risk_table.md)
Needs TABPFN_API_KEY in .env for the TabPFN row.
"""
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import make_column_transformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.data import CATEGORICAL, FEATURES, NUMERIC, TARGET, load, time_split  # noqa: E402

N_TRAIN, N_TEST, SEED = 10_000, 5_000, 0   # TabPFN reads its training rows on every call, so keep it modest

df = load()
train_all, test_all = time_split(df)
train = train_all.sample(N_TRAIN, random_state=SEED)
# Graded on no-deposit bookings only: a guest who paid up front and cancels costs the owner nothing,
# and non-refundable bookings cancel 99.4% of the time here, which floods every model's top 10%.
test = test_all[test_all.deposit_type == "No Deposit"].sample(N_TEST, random_state=SEED)
y_te = test[TARGET].to_numpy()


def top10_hit_rate(score, y):
    k = len(score) // 10
    return y[np.argsort(score)[::-1][:k]].mean()


def auc_ci(score, y, n=1000):
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(y), (n, len(y)))
    vals = [roc_auc_score(y[i], score[i]) for i in idx]
    return np.percentile(vals, [2.5, 97.5])


logistic = make_pipeline(
    make_column_transformer((OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAL),
                            (StandardScaler(), NUMERIC)),
    LogisticRegression(max_iter=2000))
models = {
    "Always guess the usual rate": DummyClassifier(strategy="prior"),
    "Logistic regression": logistic,
    "Gradient boosting": HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=SEED),
    "Gradient boosting, all training rows": HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=SEED),
}

load_dotenv(ROOT / ".env")
if os.getenv("TABPFN_API_KEY"):
    import tabpfn_client
    from tabpfn_client import TabPFNClassifier
    tabpfn_client.set_access_token(os.environ["TABPFN_API_KEY"])
    models["TabPFN (API)"] = TabPFNClassifier()

rows = []
for name, model in models.items():
    t0 = time.time()
    rows_used = train_all if "all training rows" in name else train
    model.fit(rows_used[FEATURES], rows_used[TARGET])
    score = model.predict_proba(test[FEATURES])[:, 1]
    secs = time.time() - t0
    auc = roc_auc_score(y_te, score)
    lo, hi = auc_ci(score, y_te) if auc != 0.5 else (0.5, 0.5)
    rows.append((name, f"{len(rows_used):,}", f"{auc:.3f}", f"{lo:.3f}–{hi:.3f}",
                 f"{top10_hit_rate(score, y_te):.0%}", f"{secs:.1f}"))
    print(rows[-1], flush=True)

table = pd.DataFrame(rows, columns=["Model", "Rows learned from", "ROC-AUC", "95% range",
                                    "Top-10% hit rate", "Seconds"])
note = (f"Learned from {N_TRAIN:,} arrivals before 1 Jan 2017 (sampled from {len(train_all):,}); "
        f"tested on {N_TEST:,} no-deposit arrivals from 1 Jan 2017 (sampled from {len(test_all):,} arrivals). "
        f"{y_te.mean():.1%} of test bookings cancelled. Seed {SEED}.")
out = ROOT / "results/risk_table.md"
out.write_text("# Risk model comparison\n\n" + note + "\n\n" + table.to_markdown(index=False) + "\n")
print("\n" + out.read_text())
