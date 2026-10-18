"""Send the morning summary to the owner's Telegram now, after a short wait, for recording the demo on a phone.
The text is exactly what the 08:00 message says (noshow/bot.py summary()), built from the saved demo morning
(results/demo_snapshot.json), so it needs no TabPFN call and doesn't touch the desk's database.

Run: .venv/bin/python scripts/ping_telegram.py            (sends in 20 s; start the phone recording first)
     .venv/bin/python scripts/ping_telegram.py --in 5 --url https://no-show-desk.onrender.com/desk
     .venv/bin/python scripts/ping_telegram.py --dry      (prints the message, sends nothing)
Needs TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID in .env; neither is ever printed.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noshow import bot, desk  # noqa: E402

args = argparse.ArgumentParser()
args.add_argument("--in", dest="wait", type=float, default=20, help="seconds to wait before sending")
args.add_argument("--url", default="https://no-show-desk.onrender.com/desk", help="the page link in the message")
args.add_argument("--dry", action="store_true", help="print the message instead of sending it")
a = args.parse_args()

snap = json.loads((ROOT / "results/demo_snapshot.json").read_text())
guests = sorted(snap["morning"], key=lambda g: -g["risk"])
flagged = [g for g in guests if g["flagged"]]
nights = lambda b: b["stays_in_weekend_nights"] + b["stays_in_week_nights"]
total = f"${sum(round(g['booking']['adr'] * nights(g['booking']), 2) for g in flagged):,.2f}"
text = bot.summary(guests, desk.FLAG_LINE, a.url, total)

if a.dry:
    print(text)
    sys.exit()

load_dotenv(ROOT / ".env")
token, owner = os.getenv("TELEGRAM_BOT_TOKEN"), bot.owner_id()
if not token or owner is None:
    sys.exit("TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID must be set in .env")


async def send():
    from telegram import Bot
    print(f"Sending in {a.wait:.0f} s…", flush=True)
    await asyncio.sleep(a.wait)
    async with Bot(token) as b:
        await b.send_message(chat_id=owner, text=text)
    print("Sent.")

asyncio.run(send())
