"""Data card: what is in the bookings file, and which columns give the answer away.

Run: .venv/bin/python scripts/data_card.py  (writes results/data_card.md)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data/raw/hotels.csv")
arr = pd.to_datetime(df.arrival_date_year.astype(str) + "-" + df.arrival_date_month + "-"
                     + df.arrival_date_day_of_month.astype(str), format="%Y-%B-%d")

lines = ["# Data card: Hotel booking demand", "",
         f"- Rows: {len(df):,}; columns: {df.shape[1]}",
         f"- Hotels: {df.hotel.value_counts().to_dict()}",
         f"- Arrivals from {arr.min():%d %b %Y} to {arr.max():%d %b %Y}",
         f"- Cancelled (is_canceled = 1): {df.is_canceled.mean():.1%}", "",
         "## Does 'cancelled' include no-shows?", "",
         pd.crosstab(df.reservation_status, df.is_canceled).to_markdown(), "",
         "## Columns that may hold the answer (cancel rate by value)", ""]

def rate(col, groups):
    return {k: f"{v:.1%} of {n:,}" for k, (v, n) in groups.items()}

checks = {
    "required_car_parking_spaces > 0": df.groupby(df.required_car_parking_spaces > 0).is_canceled.agg(["mean", "size"]),
    "country is PRT (Portugal)": df.groupby(df.country == "PRT").is_canceled.agg(["mean", "size"]),
    "assigned_room_type != reserved_room_type": df.groupby(df.assigned_room_type != df.reserved_room_type).is_canceled.agg(["mean", "size"]),
    "booking_changes > 0": df.groupby(df.booking_changes > 0).is_canceled.agg(["mean", "size"]),
    "deposit_type": df.groupby("deposit_type").is_canceled.agg(["mean", "size"]),
}
for name, t in checks.items():
    lines.append(f"- **{name}**: " + "; ".join(f"{k}: {m:.1%} of {n:,}" for k, (m, n) in t.iterrows()))

out = ROOT / "results/data_card.md"
out.write_text("\n".join(lines) + "\n")
print(out.read_text())
