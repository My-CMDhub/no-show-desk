"""Gemma writes the words. Two ways of briefing it, so we can measure which one gets the facts right."""
import os

from langchain_ollama import ChatOllama

from noshow.facts import FREE_CANCEL_DAYS, as_note

MODEL = os.getenv("DRAFT_MODEL", "gemma4:e2b-it-qat")   # 4.3 GB build that fits an 8 GB Mac

SYSTEM = ("You write one short text message from a small motel to a guest who has an upcoming booking. "
          "Friendly and plain, under 60 words, no emojis. Mention the arrival and departure dates, the "
          "number of nights, the total price and the last day they can cancel for free. Ask them to reply "
          "YES to keep the room. Use only the details you are given. Write the message only.")


def facts_brief(facts: dict) -> str:
    """After: every date and amount already worked out in code."""
    return "Booking details:\n" + as_note(facts)


def raw_brief(b: dict) -> str:
    """Before: the booking as the system stores it; the model has to work things out."""
    return ("Booking record:\n"
            f"Guest: {b['guest']}\nRoom type: {b['reserved_room_type']}\n"
            f"arrival_date: {b['arrival']:%Y-%m-%d}\n"
            f"stays_in_weekend_nights: {b['stays_in_weekend_nights']}\n"
            f"stays_in_week_nights: {b['stays_in_week_nights']}\n"
            f"average_daily_rate: {b['adr']}\n"
            f"Policy: free cancellation until {FREE_CANCEL_DAYS} days before arrival.")


def write_draft(brief: str, model: str = MODEL, temperature: float = 0.7, seed: int | None = None) -> str:
    llm = ChatOllama(model=model, temperature=temperature, seed=seed, num_ctx=2048)  # short context keeps it inside 8 GB
    return llm.invoke([("system", SYSTEM), ("human", brief)]).content.strip()
