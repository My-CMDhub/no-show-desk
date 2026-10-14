"""Telegram: the owner's side of the desk. /morning runs the desk; each flagged guest arrives as a
card with Approve / Edit / Reject. A button press resumes that booking's paused graph run.

Run: .venv/bin/python -m noshow.bot   then send /start to your bot.
Nothing is ever sent to a guest: an approved message goes to the outbox file only.
"""
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from noshow import desk

ROOT = Path(__file__).resolve().parents[1]
OUTBOX = ROOT / "data/outbox.jsonl"
DEMO_DAY = os.getenv("DEMO_DAY", "2017-03-06")


def owner_id() -> int | None:
    """The owner is pinned in .env, never claimed by whoever messages the bot first."""
    raw = os.getenv("TELEGRAM_OWNER_ID", "")
    return int(raw) if raw.isdigit() else None


def is_owner(update: Update) -> bool:
    user, chat = update.effective_user, update.effective_chat
    return bool(user and chat and chat.type == "private" and user.id == owner_id())


def card(w: dict) -> tuple[str, InlineKeyboardMarkup]:
    flag = ("\n\n⚠️ Check failed: " + "; ".join(w["problems"])) if w["problems"] else ""
    text = f"{w['guest']} · cancel risk {w['risk']:.0%}\n\n{w['draft']}{flag}"
    buttons = [[InlineKeyboardButton("Approve", callback_data=f"approve|{w['id']}"),
                InlineKeyboardButton("Edit", callback_data=f"edit|{w['id']}"),
                InlineKeyboardButton("Reject", callback_data=f"reject|{w['id']}")]]
    return text, InlineKeyboardMarkup(buttons)


def resume(thread: str, answer) -> dict:
    out = desk.app().invoke(Command(resume=answer), {"configurable": {"thread_id": thread}})
    if out.get("final"):
        with OUTBOX.open("a") as f:
            f.write(json.dumps({"id": thread, "guest": out["booking"]["guest"], "text": out["final"]}) + "\n")
    return out


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if owner_id() is None and update.effective_chat.type == "private":
        await update.message.reply_text(f"Your Telegram user id is {update.effective_user.id}. Add "
                                        f"TELEGRAM_OWNER_ID={update.effective_user.id} to .env and restart the bot.")
        return
    if not is_owner(update):
        return
    await update.message.reply_text("No-Show Desk is ready. Send /morning to check upcoming bookings.")


async def morning(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(f"Checking bookings arriving in the {desk.DAYS_AHEAD} days from {DEMO_DAY}…")
    results = await asyncio.to_thread(desk.morning, DEMO_DAY)
    flagged = sum(r["paused"] for r in results)
    await update.message.reply_text(f"{len(results)} bookings checked, {flagged} need a message from you.")
    for w in await asyncio.to_thread(desk.pending):
        text, kb = card(w)
        await update.message.reply_text(text, reply_markup=kb)


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_owner(update):
        await q.answer()
        return
    await q.answer()
    action, thread = q.data.split("|", 1)
    if action == "edit":
        ctx.user_data["editing"] = thread
        await q.message.reply_text("Send the message as you want it to read.")
        return
    await asyncio.to_thread(resume, thread, action)
    verdict = "Saved to outbox ✓" if action == "approve" else "Rejected, nothing saved"
    await q.edit_message_text(f"{q.message.text}\n\n— {verdict}")


async def edited(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    thread = ctx.user_data.pop("editing", None)
    if not thread:
        return
    await asyncio.to_thread(resume, thread, {"decision": "edit", "text": update.message.text})
    await update.message.reply_text("Your version is saved to the outbox ✓")


def main():
    load_dotenv(ROOT / ".env")
    bot = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("morning", morning))
    bot.add_handler(CallbackQueryHandler(button))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, edited))
    bot.run_polling()


if __name__ == "__main__":
    main()
