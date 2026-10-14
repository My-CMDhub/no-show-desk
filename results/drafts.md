# Before / after: facts worked out in code

50 no-deposit bookings from 2017 × 2 drafts each × 2 briefs. Model: gemma4:e2b-it-qat.
Scored with the current checker (it learned numeric and abbreviated dates after the first read-through).

| Brief | Drafts | With a wrong or missing fact | Median seconds |
|---|---|---|---|
| Raw booking record (model works it out) | 100 | 13 (13%) | 35.3 |
|  ↳ problem kinds | | {'date': 11, 'amount': 3, 'says': 2} | |
| Facts worked out in code | 100 | 0 (0%) | 29.9 |
|  ↳ problem kinds | | {} | |
