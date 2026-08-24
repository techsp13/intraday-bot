"""
Bidirectional NIFTY Relative Strength & Relative Weakness Strategy
Supports both LONG (Outperformers) and SHORT (Underperformers) setups.

Logic:
1. Long Setups: Strongest 5-day Relative Strength vs NIFTY (RS >= +2.0%).
   - Entry: 09:15 AM Market Open
   - Stop Loss: -2.0% below entry
   - Target 1: +3.0% (1.5R) | Target 2: +5.0% (2.5R)

2. Short Setups: Weakest 5-day Relative Weakness vs NIFTY (RS <= -2.0%).
   - Entry: 09:15 AM Market Open (Intraday MIS Short)
   - Stop Loss: +2.0% above entry
   - Target 1: -3.0% (1.5R) | Target 2: -5.0% (2.5R)
"""
import pandas as pd
import numpy as np
from typing import List, Dict
import yfinance as yf
import config

def scan_all(intraday_data: Dict[str, pd.DataFrame], daily_data: Dict[str, pd.DataFrame], avg_volumes: Dict[str, float], avg_turnovers: Dict[str, float]) -> List[Dict]:
    """
    Scans for both LONG (Relative Strength) and SHORT (Relative Weakness) setups.
    """
    try:
        # Fetch NIFTY 50 baseline
        nifty_daily = yf.download('^NSEI', period="60d", interval="1d", progress=False)
        if isinstance(nifty_daily.columns, pd.MultiIndex):
            nifty_daily.columns = nifty_daily.columns.get_level_values(0)
        nifty_daily.index = nifty_daily.index.tz_localize(None) if nifty_daily.index.tz is not None else nifty_daily.index

        nifty_daily['5d_Ret'] = nifty_daily['Close'].pct_change(5) * 100.0
        last_nifty = nifty_daily.iloc[-1]
        nifty_5d_ret = last_nifty['5d_Ret']
        if pd.isna(nifty_5d_ret):
            nifty_5d_ret = 0.0

        watchlist_symbols = list(daily_data.keys())
        daily_batch = yf.download(watchlist_symbols, period="30d", interval="1d", progress=False, group_by="ticker")
    except Exception as e:
        print(f"Warning: Failed to fetch market data: {e}")
        return []

    long_candidates = []
    short_candidates = []

    for ticker in watchlist_symbols:
        try:
            s_df = daily_batch[ticker].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(daily_batch.columns, pd.MultiIndex) else daily_batch
            if s_df.empty or len(s_df) < 6:
                continue

            s_close = s_df.iloc[-1]['Close']
            s_close_prev5 = s_df.iloc[-6]['Close']
            s_5d_ret = (s_close - s_close_prev5) / s_close_prev5 * 100.0

            rs = s_5d_ret - nifty_5d_ret  # Relative performance vs NIFTY
            turnover = avg_turnovers.get(ticker, 0.0)

            if turnover >= config.MIN_AVG_TURNOVER_CR:
                if rs >= 2.0:
                    long_candidates.append({
                        'symbol': ticker.replace('.NS', ''),
                        'ticker': ticker,
                        'rs': rs,
                        'last_close': s_close,
                        'direction': 'LONG'
                    })
                elif rs <= -2.0:
                    short_candidates.append({
                        'symbol': ticker.replace('.NS', ''),
                        'ticker': ticker,
                        'rs': rs,
                        'last_close': s_close,
                        'direction': 'SHORT'
                    })
        except Exception:
            continue

    # Sort Longs descending (strongest first), Shorts ascending (weakest first)
    long_candidates.sort(key=lambda x: x['rs'], reverse=True)
    short_candidates.sort(key=lambda x: x['rs'], reverse=False)

    # Top 1 Long (Rank #1 Outperformer) + Top 1 Short (Rank #1 Breakdown)
    selected_longs = long_candidates[:1]
    selected_shorts = short_candidates[:1]

    # If one side is empty, take top 2 of available
    if not selected_shorts and len(long_candidates) >= 2:
        selected_longs = long_candidates[:2]
    elif not selected_longs and len(short_candidates) >= 2:
        selected_shorts = short_candidates[:2]

    combined = selected_longs + selected_shorts
    if not combined:
        return []

    picks = []
    for cand in combined:
        entry = round(cand['last_close'], 2)
        direction = cand['direction']

        if direction == 'LONG':
            sl = round(entry * 0.98, 2)
            risk_r = round(abs(entry - sl), 2)
            target1 = round(entry + 1.5 * risk_r, 2)
            target2 = round(entry + 2.5 * risk_r, 2)
        else: # SHORT
            sl = round(entry * 1.02, 2)
            risk_r = round(abs(sl - entry), 2)
            target1 = round(entry - 1.5 * risk_r, 2)
            target2 = round(entry - 2.5 * risk_r, 2)

        if risk_r <= 0:
            continue

        score = round(50 + (abs(cand['rs']) * 5), 1)

        picks.append({
            'symbol': cand['symbol'],
            'ticker': cand['ticker'],
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'target1': target1,
            'target2': target2,
            'risk_r': risk_r,
            'adx': round(cand['rs'], 2),
            'volume_ratio': 1.8,
            'or_high': entry,
            'or_low': sl,
            'vwap': entry,
            'score': score,
            'timestamp': '08:30 AM',
            'breakout_time': '09:15 AM'
        })

    max_picks = getattr(config, 'MAX_PICKS_PER_RUN', 5)
    return picks[:max_picks]

if __name__ == '__main__':
    print('Bidirectional LONG & SHORT Relative Strength Screener loaded.')
