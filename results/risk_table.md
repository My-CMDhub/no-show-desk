# Risk model comparison

Learned from 10,000 arrivals before 1 Jan 2017 (sampled from 78,703); tested on 5,000 no-deposit arrivals from 1 Jan 2017 (sampled from 40,687 arrivals). 31.4% of test bookings cancelled. Seed 0.

| Model                                |   Rows learned from |   ROC-AUC | 95% range   | Top-10% hit rate   |   Seconds |
|:-------------------------------------|--------------------:|----------:|:------------|:-------------------|----------:|
| Always guess the usual rate          |              10,000 |     0.5   | 0.500–0.500 | 32%                |       0   |
| Logistic regression                  |              10,000 |     0.761 | 0.747–0.776 | 71%                |       0.2 |
| Gradient boosting                    |              10,000 |     0.771 | 0.757–0.785 | 68%                |       0.7 |
| Gradient boosting, all training rows |              78,703 |     0.782 | 0.769–0.795 | 71%                |       1.2 |
| TabPFN (API)                         |              10,000 |     0.784 | 0.771–0.798 | 69%                |      23.1 |
