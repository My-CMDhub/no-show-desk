# No-Show Desk

Every morning it reads a small motel's upcoming bookings, scores which guests are likely to cancel or not turn up, and drafts a short confirmation message for each of them. The owner approves every message on Telegram. Nothing is sent on its own.

- **Risk score:** TabPFN, learned from past bookings ([results](results/))
- **Facts:** nights, total and free-cancellation date worked out in plain code (`noshow/facts.py`)
- **Words:** Gemma 4, running locally through Ollama (`noshow/draft.py`)
- **Check:** a plain-Python check that every date and amount in the draft matches the facts (`noshow/check.py`)
- **Flow:** a LangGraph graph that pauses for the owner's approval (`noshow/graph.py`)

Data: [Hotel booking demand](https://www.kaggle.com/datasets/jessemostipak/hotel-booking-demand) (Antonio, Almeida & Nunes, *Data in Brief* 22, 2019; CC BY 4.0). Two Portuguese hotels, not motels.

Work in progress for the DEV Hacktoberfest 2026 "Side Hustle" challenge.
