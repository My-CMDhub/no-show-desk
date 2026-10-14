# Spike: Gemma 4 E2B in the browser (14 Oct)

Same first 20 bookings and wording as `drafts_reconfirm.md` (facts from code, seen 0–2 days before arrival), one draft
each (seed 1), same checker. Model: `gemma-4-E2B-it-web.litertlm` (2.0 GB) through LiteRT-LM 0.18.0 on WebGPU, in
the Claude desktop app's built-in Chromium 152 browser, 8 GB M2 Mac (Apple Metal 3), Ollama unloaded. Sampler: top-p
0.95, top-k 64, temperature 0.7 (Ollama's Gemma defaults). Model served from local disk.

| | Browser (LiteRT-LM) | Ollama (QAT, same 20 bookings, from drafts_reconfirm) |
|---|---|---|
| Drafts with a wrong or missing fact (checker) | 0 of 20 | 0 of 20 (0 of 100 overall) |
| Hand read | 0 wrong facts; 6 of 6 open free-cancel dates mentioned, 0 closed ones | 0 wrong facts |
| Median seconds per draft | 2.9 (first draft 28.6, warm-up) | ~31 |
| Model load | 9.4 s from local disk; a first visit over the internet adds the 2.0 GB download | n/a |

Wording slips (not fact errors): 1 clumsy ([12] "confirming your arrival at the motel from April 3rd to April 10th").
Drafts are more uniform ("just confirming your stay…" in 13 of 20).

Limits: 20 drafts, one seed, one machine and browser. The 100-draft rerun is the measure to quote; this is the go/no-go.
