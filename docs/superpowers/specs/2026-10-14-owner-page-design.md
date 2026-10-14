# Owner page, reasons and morning ping: design (approved 14 Oct 2026)

## What changes
- **Flag rule:** risk 30% or more (was: top 5). Measured on the same 30 test mornings
  (`results/thresholds.md`): 3–13 guests a morning, never zero; 53% of flagged guests cancelled
  (random: 29%); catches 111 of 172 cancellations (65%), top 5 caught 84 (49%).
- **Drafting is on demand.** The morning run uses no Gemma; a draft is made only when the owner presses Draft.

## Flow: one LangGraph run per guest, two pauses
`triage → (flagged) choose ⏸ → facts → draft → check (one retry) → review ⏸ → END`
- **Pause 1, choose:** `draft` continues; `leave` ends the run, outcome `left` (no draft ever made).
- **Pause 2, review:** `send` (optionally with edited text) → outcome `sent`, written to the outbox with a
  mock channel and time; `reject` → outcome `rejected`, draft discarded, nothing sent.
- Leave and Reject are different actions at different pauses with different stored outcomes.

## Reasons (`noshow/reasons.py`, code only, never the model)
Compare the booking with the history TabPFN learned from, no-deposit bookings only. Factors: lead-time
band, previous cancellations, booking channel (market segment), repeat guest, special requests.
Keep a factor when its group has ≥ 30 bookings and cancelled ≥ 5 points above the overall rate;
show up to 3, biggest gap first. None qualify → "No single factor stands out; the score comes from
the combination." The page says reasons describe past bookings, not the model's internals.

## Morning ping (Telegram)
Daily at `MORNING_AT` (default 08:00) while the app runs, and on `/morning`. One message: how many of
the day's guests are 30%+; each flagged guest's name, risk, arrival, top reason; link to the page. No buttons.

## Owner page (FastAPI + one HTML file, no build step)
- Header: demo day, "N of 20 flagged", ROI line from the 30 test mornings, labelled as historical data.
- One card per flagged guest, riskiest first: risk, arrival, nights, total, room, channel, lead time,
  fictional contact (WhatsApp number or email), reasons, **Draft / Leave**.
- After Draft (~30 s, progress shown): editable draft + checker verdict, **Send / Reject**.
- Sent: "Sent via WhatsApp to +61 4xx… · 09:14" plus a grey "demo: not delivered" tag.
- Unflagged guests in a collapsed list with their risk.
- One command runs page, bot and schedule: `python -m noshow.app`. Demo day fixed in `.env` (data is 2017).

## Tests
Reasons (unit, test-first); two-pause graph with a stand-in writer; page endpoints with FastAPI's
TestClient; Telegram summary text. Then one live run (real TabPFN + Gemma) and a browser check.

## Out of scope
Real WhatsApp/email delivery, threshold slider, WebGPU, more than one motel. Video and post come after.
