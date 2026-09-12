"""
Bidirectional NIFTY Relative Strength & Relative Weakness Strategy.
Supports:
1. 08:30 AM Full Watchlist (All Top 5 Stocks: Top 3 Longs + Top 2 Shorts).
2. 08:45 AM Final Filtered Picks (Top 2 Best Stocks: Rank #1 Long + Rank #1 Short).
Includes Entry Range Zones (±0.5% tolerance) for stress-free execution at market open.
"""
import pandas as pd
import numpy as np
from typing import List, Dict
import config
from angel_data_feed import get_candle_df

def scan_all(intraday_data: Dict[str, pd.DataFrame], daily_data: Dict[str, pd.DataFrame], avg_volumes: Dict[str, float], avg_turnovers: Dict[str, float], top2_only: bool = False) -> List[Dict]:
    """
    Scans for both LONG (Relative Strength) and SHORT (Relative Weakness) setups using AngelOne SmartAPI.
    top2_only=False -> Full 5-Stock Watchlist for 08:30 AM
    top2_only=True  -> Final Top 2 Filtered Picks for 08:45 AM
    """
    try:
        # Fetch NIFTY 50 baseline via AngelOne
        nifty_daily = get_candle_df('^NSEI', interval='ONE_DAY', days_back=60)
        if nifty_daily.empty:
            print("Warning: Could not fetch NIFTY 50 data from AngelOne.")
            return []

        col_close = 'close' if 'close' in nifty_daily.columns else 'Close'
        nifty_daily['5d_Ret'] = nifty_daily[col_close].pct_change(5) * 100.0
        last_nifty = nifty_daily.iloc[-1]
        nifty_5d_ret = last_nifty['5d_Ret']
        if pd.isna(nifty_5d_ret):
            nifty_5d_ret = 0.0

        watchlist_symbols = list(daily_data.keys())
    except Exception as e:
        print(f"Warning: Failed to fetch market data from AngelOne: {e}")
        return []

    long_candidates = []
    short_candidates = []

    for ticker in watchlist_symbols:
        try:
            # Use daily_data passed in, or fetch directly from AngelOne
            s_df = daily_data.get(ticker)
            if s_df is None or s_df.empty or len(s_df) < 6:
                s_df = get_candle_df(ticker, interval='ONE_DAY', days_back=30)
            if s_df.empty or len(s_df) < 6:
                continue

            c_col = 'close' if 'close' in s_df.columns else 'Close'
            s_close = float(s_df.iloc[-1][c_col])
            s_close_prev5 = float(s_df.iloc[-6][c_col])
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
        # Full 08:30 AM Watchlist (Top 5 Best Setups: Top 3 Longs + Top 2 Shorts)
        selected_longs = long_candidates[:3]
        selected_shorts = short_candidates[:2]
        if len(selected_shorts) < 2 and len(long_candidates) > 3:
            selected_longs = long_candidates[:5 - len(selected_shorts)]
        if len(selected_longs) < 3 and len(short_candidates) > 2:
            selected_shorts = short_candidates[:5 - len(selected_longs)]
        combined = selected_longs + selected_shorts

    if not combined:
        return []

    picks = []
    for cand in combined:
        entry = round(cand['last_close'], 2)
        direction = cand['direction']
        entry_min = round(entry * 0.995, 2) # -0.5% lower entry bound
        entry_max = round(entry * 1.005, 2) # +0.5% upper entry bound

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
            'entry_min': entry_min,
            'entry_max': entry_max,
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
            'timestamp': '08:45 AM' if top2_only else '08:30 AM',
            'breakout_time': '09:15 AM'
        })

    return picks

if __name__ == '__main__':
    print('Screener loaded with Entry Range Zones (±0.5% tolerance).')
