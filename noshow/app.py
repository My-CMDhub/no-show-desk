"""The owner's page and the API behind it. One process runs the page, the Telegram bot and the morning ping.

Run: .venv/bin/python -m noshow.app   then open http://localhost:8000
The page has no login, so it listens on this computer only.
"""
import os
import threading
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from noshow import bot, desk

PAGE = Path(__file__).with_name("page.html")
GEMMA = threading.Lock()   # one Gemma job at a time on an 8 GB Mac


@asynccontextmanager
async def lifespan(api: FastAPI):
    load_dotenv(desk.ROOT / ".env")
    api.state.desk = desk.app()
    stop = await bot.start(api.state.desk) if os.getenv("TELEGRAM_BOT_TOKEN") else None
    yield
    if stop:
        await stop()


api = FastAPI(lifespan=lifespan)
api.mount("/fonts", StaticFiles(directory=PAGE.with_name("fonts")), name="fonts")   # Overpass, SIL OFL (fonts/OFL.txt)


class Edit(BaseModel):
    text: str | None = Field(None, max_length=1000)
    anyway: bool = False   # the owner saw the check's problems and sends regardless


@api.get("/")
def page():
    return FileResponse(PAGE, headers={"Cache-Control": "no-cache"})


@api.get("/api/day")
def day(request: Request):
    guests = desk.guests(desk.DAY, request.app.state.desk)
    return {"day": desk.DAY, "line": desk.FLAG_LINE, "days_ahead": desk.DAYS_AHEAD, "roi": desk.roi(),
            "at_risk": desk.at_risk(guests), "shared": desk.shared_reasons(guests), "guests": guests}


@api.post("/api/morning")
def morning(request: Request):
    desk.morning(desk.DAY, request.app.state.desk)
    return day(request)


@api.post("/api/guests/{thread}/{action}")
def act(thread: str, action: str, request: Request, edit: Edit | None = None):
    try:
        with GEMMA if action == "draft" else nullcontext():
            return desk.act(thread, action, edit.text if edit else None, request.app.state.desk,
                            anyway=bool(edit and edit.anyway))
    except desk.NeedsOwner as e:
        raise HTTPException(422, {"problems": e.problems})
    except ValueError as e:
        raise HTTPException(409, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
