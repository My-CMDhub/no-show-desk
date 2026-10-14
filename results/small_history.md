# ROC-AUC with a motel-sized booking history

Test: the same 5,000 no-deposit arrivals from 2017. Each size: 3 random histories.

|   history |   ('mean', 'Gradient boosting') |   ('mean', 'TabPFN') |   ('min', 'Gradient boosting') |   ('min', 'TabPFN') |   ('max', 'Gradient boosting') |   ('max', 'TabPFN') |
|----------:|--------------------------------:|---------------------:|-------------------------------:|--------------------:|-------------------------------:|--------------------:|
|       300 |                           0.682 |                0.721 |                          0.665 |               0.708 |                          0.703 |               0.727 |
|      1000 |                           0.702 |                0.766 |                          0.678 |               0.761 |                          0.727 |               0.772 |
|      3000 |                           0.747 |                0.778 |                          0.732 |               0.769 |                          0.755 |               0.784 |

TabPFN ahead in (of 3): 300 bookings: 3, 1,000 bookings: 3, 3,000 bookings: 3
