# TabPFN v2 run on the owner's computer, against the API scores the desk uses

Local: `tabpfn` with ModelVersion.V2 weights (Prior Labs License: Apache 2.0 + attribution, commercial use allowed), on MPS of an 8 GB M2 Mac. API: the scores in `morning_risks.csv` (tabpfn-client defaults). Same 30 mornings of 2017, same 600 guests, same 3,000-booking histories.

| | API (the desk's numbers) | v2 on this Mac |
|---|---|---|
| Flagged at the 30% line | 210 | 205 |
| Cancellations caught at that line, of 172 | 111 | 111 |
| Caught with the same message budget as the desk (210) | 111 | 115 |
| ROC-AUC over the 600 guests | 0.792 | 0.787 |

Score agreement: Pearson 0.967, Spearman 0.956; same side of the 30% line for 551 of 600 guests.

Demo morning (2017-02-01): API flags 7, v2 flags 6, both flag 6.

Time per morning (fit on 3,000 bookings + score 20): median 23.5 s, max 33.3 s, total 12.1 min (first morning includes loading the weights).
