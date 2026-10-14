# Data card: Hotel booking demand

- Rows: 119,390; columns: 32
- Hotels: {'City Hotel': 79330, 'Resort Hotel': 40060}
- Arrivals from 01 Jul 2015 to 31 Aug 2017
- Cancelled (is_canceled = 1): 37.0%

## Does 'cancelled' include no-shows?

| reservation_status   |     0 |     1 |
|:---------------------|------:|------:|
| Canceled             |     0 | 43017 |
| Check-Out            | 75166 |     0 |
| No-Show              |     0 |  1207 |

## Columns that may hold the answer (cancel rate by value)

- **required_car_parking_spaces > 0**: False: 39.5% of 111,974.0; True: 0.0% of 7,416.0
- **country is PRT (Portugal)**: False: 23.6% of 70,800.0; True: 56.6% of 48,590.0
- **assigned_room_type != reserved_room_type**: False: 41.6% of 104,473.0; True: 5.4% of 14,917.0
- **booking_changes > 0**: False: 40.9% of 101,314.0; True: 15.7% of 18,076.0
- **deposit_type**: No Deposit: 28.4% of 104,641.0; Non Refund: 99.4% of 14,587.0; Refundable: 22.2% of 162.0
