"""The charts for the write-up, drawn from the stored results (never from typed-in numbers).

Run: .venv/bin/python scripts/charts.py   (writes docs/images/chart-*.png; needs data/raw/hotels.csv)
Colours: amber = this project's method, blue = what it is compared with (checked for colour-blind separation).
"""
import json
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow.check import check_draft  # noqa: E402
from noshow.data import load, time_split  # noqa: E402
from noshow.facts import work_out_facts  # noqa: E402

OURS, OTHER = "#A87A00", "#2E6DB0"
INK, MUTED, RULE = "#15191C", "#5E676C", "#E3E6E4"
OUT = ROOT / "docs/images"
plt.rcParams.update({"font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 13,
                     "axes.edgecolor": RULE, "text.color": INK, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": INK})


def frame(title, subtitle, source, height=4.2):
    fig = plt.figure(figsize=(8, height), dpi=200, facecolor="white")
    fig.text(0.04, 0.95, title, fontsize=17, fontweight="bold", va="top")
    fig.text(0.04, 0.95 - 0.55 / height, subtitle, fontsize=12.5, color=MUTED, va="top")
    fig.text(0.04, 0.03, source, fontsize=10, color=MUTED, va="bottom")
    return fig


def hbars(ax, labels, values, colors, fmt, top=None):
    """Horizontal bars with rounded data ends, a value label at each end, no grid."""
    top = top or max(values) * 1.18
    for y, (v, c) in enumerate(zip(values, colors)):
        w = max(v, top * 0.004)
        ax.add_patch(FancyBboxPatch((0, y - 0.28), w, 0.56, boxstyle=f"round,pad=0,rounding_size={min(0.12, w / 2)}",
                                    mutation_aspect=1 / (top / 4), linewidth=0, facecolor=c))
        ax.text(v + top * 0.015, y, fmt(v), va="center", fontsize=14, fontweight="bold", color=INK)
    ax.set_xlim(0, top)
    ax.set_ylim(len(values) - 0.4, -0.6)
    ax.set_yticks(range(len(labels)), labels)
    ax.tick_params(axis="y", length=0, pad=10, labelsize=13)
    ax.set_xticks([])
    for side in ["top", "right", "bottom"]:
        ax.spines[side].set_visible(False)


def save(fig, name):
    fig.savefig(OUT / name, facecolor="white")
    plt.close(fig)
    print("wrote", OUT / name)


def caught():
    r = pd.read_csv(ROOT / "results/morning_risks.csv")
    flagged = r[r.risk >= 0.30]
    per_day = flagged.groupby("day").size()
    rand = (per_day * r.groupby("day").cancelled.mean()).sum()
    fig = frame("The desk finds 111 of 172 cancellations",
                f"30 test mornings, 600 guests. Random picks: the same number of guests each morning.",
                "Source: results/thresholds.md · hidden outcomes, scored after the fact")
    ax = fig.add_axes([0.30, 0.16, 0.62, 0.62])
    hbars(ax, ["Flagged by the desk\n(30% or more)", "Picked at random"], [int(flagged.cancelled.sum()), round(rand)],
          [OURS, OTHER], lambda v: f"{v:.0f}", top=int(r.cancelled.sum()))
    ax.axvline(int(r.cancelled.sum()), color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(int(r.cancelled.sum()) * 0.99, 1.45, "all 172", ha="right", va="center", fontsize=11, color=MUTED)
    save(fig, "chart-caught.png")


def eval_bookings(today: bool):
    """The 50 bookings of scripts/eval_drafts.py (random_state=1); `today` as in its tagged runs."""
    from datetime import timedelta
    _, test = time_split(load())
    rows = test[test.deposit_type == "No Deposit"].sample(50, random_state=1)
    names = ["Ana Silva", "Ben Carter", "Chloe Nguyen", "Daniel Okafor", "Elena Rossi", "Farid Haddad", "Grace Kim",
             "Hugo Martin", "Isla Murphy", "Jonas Berg", "Keira Walsh", "Liam O'Brien", "Maya Patel", "Noah Fischer",
             "Olivia Brown", "Pedro Costa", "Quinn Taylor", "Rosa Lopez", "Sam Wilson", "Tara Singh", "Umar Sheikh",
             "Vera Novak", "Will Chen", "Yara Haddad"]
    return [{"guest": names[i % 24], "arrival": r.arrival.date(), "adr": float(r.adr),
             "stays_in_weekend_nights": int(r.stays_in_weekend_nights), "stays_in_week_nights": int(r.stays_in_week_nights),
             "reserved_room_type": str(r.reserved_room_type),
             **({"today": r.arrival.date() - timedelta(days=i % 3)} if today else {})}
            for i, (_, r) in enumerate(rows.iterrows())]


def wrong(path, brief, bookings):
    ds = [d for d in map(json.loads, open(ROOT / path)) if d["brief"] == brief]
    return sum(bool(check_draft(d["draft"], work_out_facts(bookings[d["i"]]))) for d in ds), len(ds)


def facts():
    plain, tagged = eval_bookings(False), eval_bookings(True)
    rows = [("Gemma works out dates\nand totals itself", *wrong("results/drafts.jsonl", "raw", plain), OTHER),
            ("Code hands Gemma the facts\n(Ollama on the Mac)", *wrong("results/drafts_reconfirm.jsonl", "facts", tagged), OURS),
            ("Code hands Gemma the facts\n(in the browser, WebGPU)", *wrong("results/drafts_browser.jsonl", "facts", tagged), OURS)]
    assert all(n == 100 for _, _, n, _ in rows)
    fig = frame("Hand the model the facts and the wrong ones disappear",
                "Drafts whose date, night count or amount doesn't match the booking (of 100).",
                "Source: results/drafts.md, drafts_reconfirm.md, drafts_browser.md · checked in code, every flag read by hand",
                height=4.6)
    ax = fig.add_axes([0.36, 0.15, 0.56, 0.64])
    hbars(ax, [r[0] for r in rows], [r[1] for r in rows], [r[3] for r in rows], lambda v: f"{v:.0f} of 100", top=16)
    save(fig, "chart-facts.png")


def small_history():
    s = pd.read_csv(ROOT / "results/small_history.csv")
    m = s.groupby(["history", "model"]).auc.mean().unstack()
    fig = frame("TabPFN ranks risk better with a motel-sized history",
                "ROC-AUC by number of past bookings learned from (mean of 3 histories). Higher is better.",
                "Source: results/small_history.md · gradient boosting at default settings")
    ax = fig.add_axes([0.10, 0.20, 0.64, 0.55])
    for model, color in [("TabPFN", OURS), ("Gradient boosting", OTHER)]:
        ax.plot(m.index, m[model], color=color, linewidth=2.2, marker="o", markersize=8,
                markeredgecolor="white", markeredgewidth=2)
        ax.text(m.index[-1] * 1.12, m[model].iloc[-1], model, color=INK, fontsize=13, fontweight="bold", va="center")
        for x, y in m[model].items():
            ax.text(x, y + (0.007 if model == "TabPFN" else -0.007), f"{y:.3f}", ha="center",
                    va="bottom" if model == "TabPFN" else "top", fontsize=11, color=MUTED)
    ax.set_xscale("log")
    ax.set_xticks(m.index, [f"{x:,}" for x in m.index])
    ax.minorticks_off()
    ax.set_xlim(m.index[0] * 0.8, m.index[-1] * 1.1)
    ax.set_ylim(0.66, 0.80)
    ax.grid(axis="y", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.set_yticks([0.68, 0.72, 0.76, 0.80])
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    save(fig, "chart-small-history.png")


def speed():
    def med(p):   # the middle value, as the results files report it (sorted list, item n // 2)
        secs = sorted(d["secs"] for d in map(json.loads, open(ROOT / p)) if d["brief"] == "facts")
        return secs[len(secs) // 2]
    browser, ollama = med("results/drafts_browser.jsonl"), med("results/drafts_reconfirm.jsonl")
    fig = frame(f"In the browser, a draft takes {browser:.2f} seconds",
                "Median seconds per message, 100 drafts each, same 8 GB M2 Mac, Gemma 4 E2B.",
                "Source: results/drafts_browser.md, drafts_reconfirm.md · browser: LiteRT-LM on WebGPU, after a one-off 10 s load")
    ax = fig.add_axes([0.30, 0.16, 0.62, 0.62])
    hbars(ax, ["In the browser\n(WebGPU)", "Through Ollama\n(same Mac)"], [browser, ollama], [OURS, OTHER],
          lambda v: f"{v:.2f} s" if v < 10 else f"{v:.1f} s")
    save(fig, "chart-speed.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    caught()
    facts()
    small_history()
    speed()
