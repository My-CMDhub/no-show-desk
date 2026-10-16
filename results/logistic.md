# TabPFN against a plain logistic regression

Logistic regression: one-hot categories, scaled numbers, scikit-learn defaults otherwise. Fitted here, no API.

## 1. Motel-sized histories (ROC-AUC, mean of 3 histories; same test as small_history.md)

|   history |   Gradient boosting |   Logistic regression |   TabPFN |
|----------:|--------------------:|----------------------:|---------:|
|       300 |               0.682 |                 0.699 |    0.721 |
|      1000 |               0.702 |                 0.741 |    0.766 |
|      3000 |               0.747 |                 0.749 |    0.778 |

TabPFN ahead of logistic regression (of 3): 300 bookings: 3, 1,000 bookings: 3, 3,000 bookings: 3

## 2. The 30 test mornings of 2017 (600 guests, 172 cancelled)

Each model messages the same number of guests per morning as the desk's 30% line (210 in all).

| Model | Cancellations caught | ROC-AUC over the 600 guests |
|---|---|---|
| TabPFN | 111 of 172 | 0.792 |
| Logistic regression | 106 of 172 | 0.762 |
