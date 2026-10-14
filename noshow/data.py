"""Load the bookings and keep only what a motel knows before the guest arrives."""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data/raw/hotels.csv"
TARGET = "is_canceled"  # 1 = cancelled or no-show (data card: all 1,207 no-shows are 1)

# Written at or after the outcome, so they give the answer away (see results/data_card.md).
LEAKS = {
    "reservation_status": "is the outcome itself",
    "reservation_status_date": "date the outcome was recorded",
    "assigned_room_type": "set at check-in; differs mostly for guests who arrived",
    "booking_changes": "counted until arrival or cancellation",
    "required_car_parking_spaces": "recorded at arrival; 0.0% cancel when > 0",
    "country": "mostly filled in at check-in; cancelled bookings default to Portugal",
}
CATEGORICAL = ["hotel", "arrival_date_month", "meal", "market_segment", "distribution_channel",
               "reserved_room_type", "deposit_type", "customer_type", "agent", "company"]
NUMERIC = ["lead_time", "arrival_date_week_number", "arrival_date_day_of_month",
           "stays_in_weekend_nights", "stays_in_week_nights", "adults", "children", "babies",
           "is_repeated_guest", "previous_cancellations", "previous_bookings_not_canceled",
           "days_in_waiting_list", "adr", "total_of_special_requests"]
FEATURES = CATEGORICAL + NUMERIC


def load() -> pd.DataFrame:
    df = pd.read_csv(RAW)
    df["arrival"] = pd.to_datetime(df.arrival_date_year.astype(str) + "-" + df.arrival_date_month
                                   + "-" + df.arrival_date_day_of_month.astype(str), format="%Y-%B-%d")
    for c in ["agent", "company"]:
        df[c] = df[c].fillna(0).astype(int).astype(str)
        rare = df[c].map(df[c].value_counts()) < 20     # ~300 agents; rare ones pooled as "other"
        df.loc[rare, c] = "other"
    df["children"] = df["children"].fillna(0)
    for c in CATEGORICAL:
        df[c] = df[c].astype("category")
    assert not set(LEAKS) & set(FEATURES)
    return df


def time_split(df: pd.DataFrame, cutoff: str = "2017-01-01"):
    """Learn from arrivals before the cutoff, test on arrivals after it."""
    return df[df.arrival < cutoff], df[df.arrival >= cutoff]
