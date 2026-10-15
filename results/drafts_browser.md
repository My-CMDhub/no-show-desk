# Gemma 4 E2B in the browser: the full 100 (15 Oct)

Same 50 bookings, same two seeds, same wording, same checker as `drafts_reconfirm.md` (Ollama). Only where the
model runs changes: `gemma-4-E2B-it-web.litertlm` (2.0 GB) through LiteRT-LM 0.18.0 on WebGPU, in the Claude desktop
app's Chromium 152, 8 GB M2 Mac (Apple Metal 3), Ollama not running. Sampler: top-p 0.95, top-k 64, temperature 0.7.

| | Browser (LiteRT-LM, WebGPU) | Ollama (QAT build) |
|---|---|---|
| Drafts with a wrong or missing fact (checker) | **0 of 100** | 0 of 100 |
| Wrong facts on a full hand read | 0 | 0 |
| Weekday stated wrongly | 0 | 0 |
| Open free-cancel date mentioned / closed one mentioned | 32 of 32 / 0 | 32 of 32 / 0 |
| Drafts that leave a fact out (hand-checked) | 6 (all one-night stays: no night count, or no departure date) | 5 (no departure date) |
| Median seconds per draft | **3.25** (90th percentile 4.87) | 31.4 |
| Model load | 9.8 s from local disk | n/a |

Leaving a fact out is not counted by the checker: it only requires the arrival date and the total. None of the 11
omissions changes what the guest is asked to confirm; each still has the arrival date and the total.
Wording: uniform ("just confirming your stay…" in most drafts); one clumsy phrase repeated for one booking
([12.1] and [12.2]: "confirming your arrival at the motel from April 3rd to April 10th").
