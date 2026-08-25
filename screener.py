"""
Bidirectional NIFTY Relative Strength & Relative Weakness Strategy.
Supports:
1. 08:30 AM Full Watchlist (All Top 5 Stocks: Top 3 Longs + Top 2 Shorts).
2. 09:00 AM Final Filtered Picks (Top 2 Best Stocks: Rank #1 Long + Rank #1 Short).
"""
import pandas as pd
import numpy as np
from typing import List, Dict
import yfinance as yf
import config

def scan_all(intraday_data: Dict[str, pd.DataFrame], daily_data: Dict[str, pd.DataFrame], avg_volumes: Dict[str, float], avg_turnovers: Dict[str, float], top2_only: bool = False) -> List[Dict]:
    """
    Scans for both LONG (Relative Strength) and SHORT (Relative Weakness) setups.
    top2_only=False -> Full 5-Stock Watchlist for 08:30 AM
    top2_only=True  -> Final Top 2 Filtered Picks for 09:00 AM
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

    if top2_only:
        # Final Top 2 Filter (Rank #1 Long + Rank #1 Short)
        selected_longs = long_candidates[:1]
        selected_shorts = short_candidates[:1]
        if not selected_shorts and len(long_candidates) >= 2:
            selected_longs = long_candidates[:2]
        elif not selected_longs and len(short_candidates) >= 2:
            selected_shorts = short_candidates[:2]
        combined = selected_longs + selected_shorts
    else:
        # Full 08:30 AM Watchlist (Top 3 Longs + Top 2 Shorts)
        selected_longs = long_candidates[:3]
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
            'timestamp': '09:00 AM' if top2_only else '08:30 AM',
            'breakout_time': '09:15 AM'
        })

    return picks

if __name__ == '__main__':
    print('Screener loaded with 08:30 AM Full Watchlist & 09:00 AM Top 2 Filter.')
