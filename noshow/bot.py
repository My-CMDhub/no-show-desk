"""Telegram: the morning ping. At MORNING_AT each day (and on /morning) the owner gets one message
listing the guests at or over the line, each with their top reason, and a link to the page where
they press Draft or Leave. Started by noshow.app. Nothing is ever sent to a guest from here.
"""
import asyncio
import logging
import os
from collections import Counter
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from noshow import desk


def owner_id() -> int | None:
    """The owner is pinned in .env, never claimed by whoever messages the bot first."""
    raw = os.getenv("TELEGRAM_OWNER_ID", "")
    return int(raw) if raw.isdigit() else None


def is_owner(update: Update) -> bool:
    user, chat = update.effective_user, update.effective_chat
    return bool(user and chat and chat.type == "private" and user.id == owner_id())


def summary(guests: list[dict], line: float, url: str, total: str) -> str:
    flagged = [g for g in guests if g["flagged"]]
    if not flagged:
        return f"Good morning. None of the guests arriving in the next {desk.DAYS_AHEAD} days look likely to cancel. {url}"
    names = [f"{g['booking']['guest']} ({g['risk']:.0%})" for g in flagged[:3]]
    first = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    more = f", plus {len(flagged) - 3} more" if len(flagged) > 3 else ""
    tops = Counter((g["reasons"][0]["label"], g["reasons"][0]["rate"]) for g in flagged if g["reasons"])
    shared = ""
    if tops and (top := tops.most_common(1)[0])[1] * 2 > len(flagged):
        (label, rate), _ = top
        shared = f"What most of them share: {label[0].lower() + label[1:]} ({rate:.0%} of similar past guests cancelled).\n"
    n = len(flagged)
    return (f"Good morning. {n} guest{'s' if n != 1 else ''} arriving in the next {desk.DAYS_AHEAD} days might not "
            f"show: {total} of bookings.\n\nStart with {first}{more}.\n{shared}\n"
            f"Draft a message or leave each one: {url}")


def seconds_until(hhmm: str, now: datetime) -> float:
    h, m = map(int, hhmm.split(":"))
    at = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return ((at if at > now else at + timedelta(days=1)) - now).total_seconds()


async def todays_summary(app: Application) -> str:
    guests = await asyncio.to_thread(desk.morning, desk.DAY, app.bot_data["desk"])
    return summary(guests, desk.FLAG_LINE, os.getenv("PAGE_URL", "http://localhost:8000"), desk.at_risk(guests)["total"])


async def hello(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if owner_id() is None and update.effective_chat.type == "private":
        await update.message.reply_text(f"Your Telegram user id is {update.effective_user.id}. Add "
                                        f"TELEGRAM_OWNER_ID={update.effective_user.id} to .env and restart.")
        return
    if is_owner(update):
        await update.message.reply_text("No-Show Desk is ready. You'll get a summary each morning; "
                                        "send /morning for one now.")


async def morning(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(f"Checking guests arriving in the {desk.DAYS_AHEAD} days from {desk.DAY}…")
    await update.message.reply_text(await todays_summary(ctx.application))


async def daily(app: Application):
    while True:
        await asyncio.sleep(seconds_until(os.getenv("MORNING_AT", "08:00"), datetime.now()))
        try:
            if owner_id():
                await app.bot.send_message(owner_id(), await todays_summary(app))
        except Exception:   # a failed ping must not stop tomorrow's
            logging.exception("morning ping failed")


async def start(graph):
    """Start polling and the daily ping inside the app's event loop. Returns a stop function."""
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.bot_data["desk"] = graph
    app.add_handler(CommandHandler("start", hello))
    app.add_handler(CommandHandler("morning", morning))
    await app.initialize()
    await app.bot.set_my_commands([("start", "Connect the desk to you"),
                                   ("morning", "Today's guests likely to cancel")])
    await app.start()
    await app.updater.start_polling()
    timer = asyncio.create_task(daily(app))

    async def stop():
        timer.cancel()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
    return stop
