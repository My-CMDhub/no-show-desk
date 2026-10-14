# Owner Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag guests at 30%+ with plain reasons, ping the owner on Telegram, and let them Draft/Leave then Send/Reject on one web page.

**Architecture:** One LangGraph run per guest with two pauses (choose, review). The morning run scores and pauses (no Gemma). FastAPI serves one HTML page and resumes runs; the Telegram bot only pings. One process runs page, bot and the daily timer.

**Tech Stack:** Python 3.12, pandas, TabPFN client, LangGraph + SQLite checkpointer, Ollama Gemma 4 e2b QAT, FastAPI + uvicorn, python-telegram-bot 22.

## Global Constraints
- Flag line: risk ≥ 0.30. Reasons: groups ≥ 30 bookings, ≥ 5 points above overall, max 3, no-deposit history only.
- Code computes every number; the model only phrases the draft.
- Leave (pause 1, outcome `left`, no draft) ≠ Reject (pause 2, outcome `rejected`, draft discarded).
- Sending is mocked: outbox file + "demo: not delivered" tag on screen. Contacts fictional (example.com, ACMA fiction numbers).
- One Gemma job at a time (lock around drafting). Owner pinned by TELEGRAM_OWNER_ID. Secrets: names only.
- Commits: conventional, no Co-Authored-By trailer.

## Files
- Create `noshow/reasons.py`: `reasons(booking: pd.Series, history: pd.DataFrame) -> list[dict]` with keys `label, who, rate, base, n, text`.
- Modify `noshow/graph.py`: nodes `choose` (pause 1) and `review` (pause 2) + `send`; `build(writer, sender, checkpointer)`.
- Modify `noshow/desk.py`: `FLAG_LINE = 0.30`, booking carries the page's fields + reasons + contact; `today(day)`, `act(thread, stage, answer)`, `roi()`; delete `pending()`.
- Create `noshow/app.py`: FastAPI routes + lifespan starting the bot and the daily timer. Create `noshow/page.html`.
- Modify `noshow/bot.py`: `/start`, `/morning` → `summary()` text; delete card buttons, edit and resume handlers.
- Tests: `tests/test_reasons.py`, `tests/test_graph.py` (rewrite for two pauses), `tests/test_app.py`, `tests/test_bot_owner.py` (+ summary, seconds_until).

### Task 1: Reasons (test-first)
- [ ] Write `tests/test_reasons.py`: synthetic history where 40 bookings 181–365 days ahead cancel 50% and 60 bookings ≤7 days cancel 10% (base 26%); assert the lead reason text, no reason for a short lead, none for a group < 30, non-refundable rows ignored, max 3 sorted by gap.
- [ ] Run, watch it fail (module missing). Implement. Run, pass. Commit `feat(reasons): plain reasons from past cancel rates`.

### Task 2: Two-pause graph (test-first)
- [ ] Rewrite `tests/test_graph.py`: low risk ends without pause; flagged pauses at `choose`; `leave` ends with outcome `left` and writer never called; `draft` → pauses at `review` with draft and problems; `send` calls the stand-in sender and stores outcome `sent` + sent info; `{"decision":"send","text":...}` sends the edited text; `reject` → outcome `rejected`, sender not called; wrong draft redrafted once.
- [ ] Fail, implement, pass. Commit `feat(graph): draft on demand, leave vs reject`.

### Task 3: Desk + page API (test-first)
- [ ] `tests/test_app.py` with TestClient and a temp SQLite + stand-in writer/sender: seeded day lists flagged + unflagged; draft→review; leave at review stage → 409; send→sent; unknown id → 409; `roi()` on the stored csv = 7.0 a morning, 53%, 3.7.
- [ ] Fail, implement `desk.today/act/roi`, `app.py`. Pass. Commit.

### Task 4: Page (design pass with frontend-design), Telegram summary + daily timer
- [ ] `summary()` and `seconds_until()` tests; implement; bot slimmed. Page built and checked in the browser at phone and desktop width.
- [ ] Live run: real TabPFN + Gemma on the demo day; read every draft. Commit.

### Task 5: Docs
- [ ] README (how to run, what's mocked), HANDOFF, logbook entry, requirements.txt.
