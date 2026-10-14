"""A small motel has a few thousand past bookings, not 78,000. Which model copes best?

Same no-deposit 2017 test set as eval_risk.py; training history shrunk to motel size,
3 different random histories per size. Run: .venv/bin/python scripts/eval_small_history.py
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.data import FEATURES, TARGET, load, time_split  # noqa: E402

load_dotenv(ROOT / ".env")
import tabpfn_client  # noqa: E402
from tabpfn_client import TabPFNClassifier  # noqa: E402
tabpfn_client.set_access_token(os.environ["TABPFN_API_KEY"])

SIZES, SEEDS = [300, 1000, 3000], [1, 2, 3]
train_all, test_all = time_split(load())
test = test_all[test_all.deposit_type == "No Deposit"].sample(5000, random_state=0)
y = test[TARGET].to_numpy()

rows = []
for n in SIZES:
    for seed in SEEDS:
        hist = train_all.sample(n, random_state=seed)
        for name, model in [("Gradient boosting", HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=seed)),
                            ("TabPFN", TabPFNClassifier())]:
            model.fit(hist[FEATURES], hist[TARGET])
            auc = roc_auc_score(y, model.predict_proba(test[FEATURES])[:, 1])
            rows.append({"history": n, "seed": seed, "model": name, "auc": auc})
            print(rows[-1], flush=True)

df = pd.DataFrame(rows)
df.to_csv(ROOT / "results/small_history.csv", index=False)
summary = df.groupby(["history", "model"]).auc.agg(["mean", "min", "max"]).unstack("model").round(3)
wins = df.pivot_table(index=["history", "seed"], columns="model", values="auc")
wins = (wins["TabPFN"] > wins["Gradient boosting"]).groupby("history").sum()
out = ROOT / "results/small_history.md"
out.write_text("# ROC-AUC with a motel-sized booking history\n\n"
               "Test: the same 5,000 no-deposit arrivals from 2017. Each size: 3 random histories.\n\n"
               + summary.to_markdown() + "\n\nTabPFN ahead in (of 3): "
               + ", ".join(f"{k:,} bookings: {v}" for k, v in wins.items()) + "\n")
print(out.read_text())
