# MATH-001: ROI and Net Profitability Calculation (v1.3 - Audited)

**Status:** Draft v1.3 (Corrected per Gemini Audit)  
**Version:** 1.3

## 1. Purpose
Corrected model that properly treats Broker Fee on Buy Orders as a **sunk cost**.

## 2. Core Equations (Corrected)

### Buy Leg (Sunk Cost)
TotalFees_buy = buy_price × broker_fee_rate
TotalCapitalRequired = buy_price + TotalFees_buy

### Sell Leg
TotalFees_sell = sell_price × (broker_fee_rate + sales_tax_rate)

### Net Profit
NetProfit = (sell_price - TotalFees_sell) - buy_price

### ROI
ROI = (NetProfit / buy_price) * 100

## 3. Key Fix
- Buy Order Broker Fee is now correctly modeled as immediate sunk cost.
- Capital calculation for PortfolioOptimizer is now accurate.
