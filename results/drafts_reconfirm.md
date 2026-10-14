# Before / after: facts worked out in code

50 no-deposit bookings from 2017 × 2 drafts each × the facts-from-code brief only, shipped reconfirm wording, booking seen 0–2 days before arrival. Model: gemma4:e2b-it-qat.
Scored with the current checker (it learned numeric and abbreviated dates after the first read-through).

| Brief | Drafts | With a wrong or missing fact | Median seconds |
|---|---|---|---|
| Facts worked out in code | 100 | 0 (0%) | 31.4 |
|  ↳ problem kinds | | {} | |

## Read by hand (all 100, 14 Oct)
- Wrong or missing facts: 0. Every date, weekday, night count and total matches the booking; a weekday
  audit script found 0 mismatches (the checker itself does not check weekdays).
- Free-cancel date: mentioned only when still open, and both drafts of each of those 16 bookings mention it.
- Placeholders or instruction text copied in: 0.
- Wording slips (not counted as fact errors): 2 clumsy sentences ([17.1] "This rate is free cancellation
  until…", [35.2] cancel folded into the YES request); 2 open with "your stay is confirmed" before asking for YES.

## Earlier attempt (disclosed)
The first version of this wording said "…the last day they can cancel for free if you are given one".
After 6 drafts (`drafts_reconfirm_v1_conditional_prompt.jsonl`): 1 invented a free-cancel date (checker caught it),
1 left "[Insert Date Here]" in, 1 copied "if you are given one" into the message (checker missed both; found by
reading). Fix: code decides whether cancellation is mentioned at all; the checker now catches placeholders and
copied instruction text. Re-scoring the original 200 before/after drafts with that checker changes nothing.
