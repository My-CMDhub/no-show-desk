"""The owner's page and the API behind it. One process runs the page, the Telegram bot and the morning ping.

Run: .venv/bin/python -m noshow.app   then open http://localhost:8000
The page has no login, so it listens on this computer only.
"""
import os
import re
import secrets
import threading
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from noshow import bot, desk

PAGE = Path(__file__).with_name("page.html")
LANDING = PAGE.with_name("landing.html")   # in front of the desk: what it is, and the way in
GEMMA = threading.Lock()   # one Gemma job at a time on an 8 GB Mac


@asynccontextmanager
async def lifespan(api: FastAPI):
    load_dotenv(desk.ROOT / ".env")
    api.state.desk = desk.app()
    # The hosted demo never starts the owner's Telegram bot, even when run on the owner's Mac with .env present.
    stop = await bot.start(api.state.desk) if os.getenv("TELEGRAM_BOT_TOKEN") and not desk.HOSTED else None
    yield
    if stop:
        await stop()


api = FastAPI(lifespan=lifespan)
api.mount("/fonts", StaticFiles(directory=PAGE.with_name("fonts")), name="fonts")   # Overpass, SIL OFL (fonts/OFL.txt)


class Edit(BaseModel):
    text: str | None = Field(None, max_length=1000)
    anyway: bool = False   # the owner saw the check's problems and sends regardless
    by: str | None = Field(None, pattern="^recorded$")   # Draft with the copy recorded on the owner's Mac


def visitor(request: Request, response: Response) -> str:
    """Hosted: each browser gets its own copy of the demo morning, keyed by a random cookie. Local: the owner's one desk."""
    if not desk.HOSTED:
        return ""
    v = request.cookies.get("desk")
    if not v or not re.fullmatch(r"[0-9a-f]{16}", v):   # only ids this server could have made
        v = secrets.token_hex(8)
        https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"   # hosts end TLS at a proxy
        response.set_cookie("desk", v, max_age=7 * 86400, httponly=True, samesite="lax", secure=https)
    return v


def mine(thread: str, request: Request, response: Response) -> str:
    v = visitor(request, response)
    if v and not thread.startswith(f"{v}~"):
        raise HTTPException(404, "No such guest on this desk")
    return thread


@api.get("/")
def landing():
    return FileResponse(LANDING, headers={"Cache-Control": "no-cache"})


@api.get("/desk")
def page():
    return FileResponse(PAGE, headers={"Cache-Control": "no-cache"})


@api.get("/api/day")
def day(request: Request, response: Response):
    v, graph = visitor(request, response), request.app.state.desk
    try:
        guests = desk.morning(desk.DAY, graph, visitor=v) if desk.HOSTED else desk.guests(desk.DAY, graph)
    except desk.DeskFull:
        raise HTTPException(503, "The demo is full right now. Please try again later.")
    return {"day": desk.DAY, "line": desk.FLAG_LINE, "days_ahead": desk.DAYS_AHEAD, "roi": desk.roi(),
            "at_risk": desk.at_risk(guests), "shared": desk.shared_reasons(guests), "guests": guests,
            "hosted": desk.HOSTED, "drafts": "browser" if desk.HOSTED or os.getenv("DRAFTS") == "browser" else "ollama"}


@api.post("/api/reset")
def reset(response: Response):
    """Hosted: a fresh copy of the demo morning (a new cookie; the old copy is left until the host restarts)."""
    if not desk.HOSTED:
        raise HTTPException(404, "Only on the hosted demo")
    response.delete_cookie("desk")
    return {"ok": True}


@api.get("/api/guests/{thread}/brief")
def brief(thread: str, request: Request, response: Response):
    try:
        return desk.brief(mine(thread, request, response), request.app.state.desk)
    except KeyError:
        raise HTTPException(404, "No such guest")


@api.get("/api/replay/{year}")
def replay(year: str):
    if year not in ("2016", "2017"):   # the two years with stored mornings
        raise HTTPException(404, "No stored mornings for that year")
    return desk.replay(year)


@api.post("/api/morning")
def morning(request: Request, response: Response):
    if desk.HOSTED:   # the hosted morning is made per visitor by /api/day
        raise HTTPException(404, "Not on the hosted demo")
    desk.morning(desk.DAY, request.app.state.desk)
    return day(request, response)


@api.post("/api/guests/{thread}/check")   # declared before /{action}: checking is not an action, it changes nothing
def check(thread: str, edit: Edit, request: Request, response: Response):
    try:
        return {"problems": desk.check_edit(mine(thread, request, response), edit.text or "", request.app.state.desk)}
    except ValueError as e:
        raise HTTPException(409, str(e))


@api.post("/api/guests/{thread}/{action}")
def act(thread: str, action: str, request: Request, response: Response, edit: Edit | None = None):
    thread = mine(thread, request, response)
    text = edit.text if edit else None
    if action == "draft" and text is not None and not text.strip():
        raise HTTPException(422, {"problems": ["the message is empty"]})
    if desk.HOSTED and action == "draft" and not (text or (edit and edit.by)):
        raise HTTPException(409, "The hosted desk drafts in your browser")   # no model on the host
    try:
        with GEMMA if action == "draft" and not text and not (edit and edit.by) else nullcontext():
            return desk.act(thread, action, text, request.app.state.desk,
                            anyway=bool(edit and edit.anyway), by=edit.by if edit else None)
    except desk.NeedsOwner as e:
        raise HTTPException(422, {"problems": e.problems})
    except ValueError as e:
        raise HTTPException(409, str(e))


if __name__ == "__main__":
    import uvicorn
    # Local: this computer only (the page has no login). Hosted: open, and every visitor only sees their own copy.
    uvicorn.run(api, host="0.0.0.0" if desk.HOSTED else "127.0.0.1", port=int(os.getenv("PORT", "8000")))
