# No-Show Desk

Every morning it scores a small motel's upcoming bookings and lists the guests who are 30% or more likely to cancel or not turn up, each with plain reasons from the motel's own past bookings. The owner gets the list on Telegram, then opens one page: **Draft** a short "are you still coming?" message or **Leave** the guest alone. A draft can be edited, then **Sent** or **Rejected**. Nothing is sent on its own, and in this demo nothing leaves the computer.

- **Risk score:** TabPFN, learned from past bookings ([results](results/))
- **Reasons:** past cancel rates of guests like this one, worked out in plain code (`noshow/reasons.py`)
- **Facts:** nights, total and free-cancellation date worked out in plain code (`noshow/facts.py`)
- **Words:** Gemma 4, running locally through Ollama (`noshow/draft.py`), only when the owner presses Draft
- **Check:** a plain-Python check that every date and amount in the draft matches the facts (`noshow/check.py`)
- **Flow:** a LangGraph graph per guest that pauses twice for the owner (`noshow/graph.py`)

## Run it

```bash
ollama pull gemma4:e2b-it-qat
.venv/bin/python -m noshow.app      # page at http://localhost:8000, plus the Telegram bot and 08:00 ping
```

`.env` needs `TABPFN_API_KEY`; Telegram also needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_ID` (optional: `MORNING_AT`, `DEMO_DAY`, `PAGE_URL`). Tests: `.venv/bin/python -m pytest -q`.

## What is real and what is a demo

- Real: the 2017 bookings, TabPFN's scores, the reasons, Gemma's drafts and the checks.
- Demo: the motel lives on a fixed day in 2017 (the data ends there); guest names, phone numbers (Australia's fiction range) and emails (`example.com`) are made up; **Send** writes to `data/outbox.jsonl` and the page marks it "demo: not delivered".
- The 30% line and the "about 3.7 rooms a morning" figure come from 30 test mornings on past bookings (`results/thresholds.md`), not a live motel.

Data: [Hotel booking demand](https://www.kaggle.com/datasets/jessemostipak/hotel-booking-demand) (Antonio, Almeida & Nunes, *Data in Brief* 22, 2019; CC BY 4.0). Two Portuguese hotels, not motels.

Work in progress for the DEV Hacktoberfest 2026 "Side Hustle" challenge.
