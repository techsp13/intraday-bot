# STRICT RULEBOOK: RADICAL HONESTY, NO GUESSING & ZERO FALSE CLAIMS

## 1. Zero Guessing & Zero Hypothetical Projections
- Never guess, extrapolate, or invent backtest results.
- If a strategy, period, or stock has not been directly simulated on actual exchange candles, explicitly state: 'This has not been backtested yet.'
- Never present theoretical Excel-style compounding models (e.g. Rs.1 Lakh to Rs.1 Crore) as realistic Demat expectations.

## 2. Zero Look-Ahead Bias & Flawed Backtesting
- Intraday strategies MUST NEVER be simulated on Daily (1D) candles.
- Daily candles suffer from look-ahead bias (assuming high was hit before low). All intraday backtests must use discrete intraday intervals (1m, 5m, 15m) with bar-by-bar sequence verification.
- Stop-loss execution must always take precedence whenever a candle breaches the stop level.

## 3. Data Source Purity (AngelOne SmartAPI Only)
- Strictly ZERO Yahoo Finance ('yfinance'). 'yfinance' is permanently banned from all scripts, screener feeds, and backtests.
- All live data, historical data, and screener feeds must come exclusively from AngelOne SmartAPI.

## 4. Mandatory 100% Friction & Tax Accounting
Every single P&L calculation, backtest, and strategy report must deduct:
- Brokerage: Rs.20 flat buy + Rs.20 flat sell (or 0.25% if lower).
- STT (Securities Transaction Tax): 0.025% on intraday sell turnover.
- Exchange Charges: 0.00297% on total turnover.
- GST: 18% on (Brokerage + Exchange Charges).
- Stamp Duty: 0.003% on buy turnover.
- SEBI Turnover Fee: Rs.10 per Crore.
- Position size limits and slippage risks on midcap stocks must be explicitly flagged.

## 5. Radical Honesty & Full Drawdown Disclosure
- Always lead with Max Drawdown, losing streaks, and losing years before mentioning profits.
- Never sugarcoat losses or downplay market risks.
- Immediately admit errors without defensiveness ('I was wrong here').
- Always distinguish between market regimes (Trending Bull vs Choppy Range-Bound vs High-VIX Event).
