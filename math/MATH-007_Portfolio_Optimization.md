# MATH-007: Portfolio Optimization (v1.3)

**Status:** Draft v1.3
**Version:** 1.3

## Discrete Allocation Constraint (Added)
allocated_capital_i = units_i * (buy_price_i + TotalFees_buy_i)
units_i = floor( proposed_capital_i / (buy_price_i + TotalFees_buy_i) ) ∈ ℤ≥0

## Solution Approach
1. Score opportunities
2. Continuous relaxation
3. Convert to discrete units using the floor constraint above
4. Validate constraints
