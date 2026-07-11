# MATH-005: Exit Time Estimation (v1.3)

**Status:** Draft v1.3
**Version:** 1.3

## Purpose
Single Source of Truth for Exit Time estimation.

## Equations (Corrected)
ExitTime_volume = position_size / max(daily_volume / 24, 1e-4)
ExitTime_depth  = position_size / max(total_sell_volume_remain, 1e-4)

Final estimated_hours = max(ExitTime_volume, ExitTime_depth)
