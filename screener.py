"""
NIFTY Relative Strength (RS) Momentum Screener + Market Regime Filter
Applies the 1-line NIFTY Daily 20 EMA > 50 EMA regime filter.
Pauses stock buys when broader market is in correction.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import yfinance as yf
import config

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    pv = tp * df['Volume']
    dates = df.index.date
    cum_pv = pv.groupby(dates).cumsum()
    cum_vol = df['Volume'].groupby(dates).cumsum()
    cum_vol_safe = np.where(cum_vol == 0, 1.0, cum_vol)
    vwap = cum_pv / cum_vol_safe
    return pd.Series(vwap, index=df.index)

def scan_all(intraday_data: Dict[str, pd.DataFrame], daily_data: Dict[str, pd.DataFrame], avg_volumes: Dict[str, float], avg_turnovers: Dict[str, float]) -> List[Dict]:
    """
    Scans for NIFTY RS Outperformers ONLY when NIFTY Index Daily 20 EMA > 50 EMA (Bull Market Regime).
    """
    try:
        # Fetch Nifty Index daily data for Market Regime Filter
        nifty_daily = yf.download('^NSEI', period="60d", interval="1d", progress=False)
        if isinstance(nifty_daily.columns, pd.MultiIndex):
            nifty_daily.columns = nifty_daily.columns.get_level_values(0)
        nifty_daily.index = nifty_daily.index.tz_localize(None) if nifty_daily.index.tz is not None else nifty_daily.index

        # Calculate Nifty Daily 20 EMA & 50 EMA
        nifty_ema20 = nifty_daily['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
        nifty_ema50 = nifty_daily['Close'].ewm(span=50, adjust=False).mean().iloc[-1]

        # ── REGIME FILTER ── Pause buys if Nifty is in correction
        if nifty_ema20 <= nifty_ema50:
            print("MARKET REGIME PAUSE: NIFTY Daily 20 EMA <= 50 EMA (Market Correction). No stock picks today.")
            return []

        # Fetch NIFTY 50 15m intraday data for RS calculation
        nifty_df = yf.download('^NSEI', period="5d", interval="15m", progress=False)
        if isinstance(nifty_df.columns, pd.MultiIndex):
            nifty_df.columns = nifty_df.columns.get_level_values(0)
        nifty_df.index = nifty_df.index.tz_localize(None) if nifty_df.index.tz is not None else nifty_df.index
    except Exception as e:
        print(f"Warning: Failed to fetch Nifty index: {e}")
        return []

    if nifty_df.empty:
        return []

    latest_date = nifty_df.index[-1].date()
    nifty_today = nifty_df[nifty_df.index.date == latest_date]
    if len(nifty_today) < 2:
        return []

    nifty_open = nifty_today.iloc[0]['Open']
    nifty_945 = nifty_today.iloc[1]['Close']
    nifty_ret = (nifty_945 - nifty_open) / nifty_open * 100.0

    stock_rs_list = []

    for ticker, df in intraday_data.items():
        if df.empty: continue
        df_clean = df.copy()
        df_clean.index = df_clean.index.tz_localize(None) if df_clean.index.tz is not None else df_clean.index
        day_df = df_clean[df_clean.index.date == latest_date]
        if len(day_df) < 6: continue

        s_open = day_df.iloc[0]['Open']
        s_945 = day_df.iloc[min(5, len(day_df)-1)]['Close']
        s_ret = (s_945 - s_open) / s_open * 100.0
        rs = s_ret - nifty_ret

        turnover = avg_turnovers.get(ticker, 0.0)
        if turnover >= config.MIN_AVG_TURNOVER_CR and rs >= 1.2:
            stock_rs_list.append({
                'ticker': ticker,
                'rs': rs,
                'day_df': day_df
            })

    if not stock_rs_list:
        return []

    stock_rs_list.sort(key=lambda x: x['rs'], reverse=True)
    top_candidates = stock_rs_list[:10]

    picks = []

    for cand in top_candidates:
        ticker = cand['ticker']
        display_symbol = ticker.replace('.NS', '')
        day_df = cand['day_df'].copy()

        day_df['EMA20'] = day_df['Close'].ewm(span=20, adjust=False).mean()
        day_df['EMA50'] = day_df['Close'].ewm(span=50, adjust=False).mean()
        vwap_series = calculate_vwap(day_df)

        session = day_df.between_time('09:45', '15:30')
        if session.empty: continue

        for dt, row in session.iterrows():
            close = row['Close']
            low = row['Low']
            ema20 = row['EMA20']
            ema50 = row['EMA50']
            vwap_val = vwap_series.loc[dt]

            if ema20 > ema50 and abs(low - ema20)/ema20 <= 0.005 and close > ema20:
                entry = round(close, 2)
                sl = round(entry * 0.992, 2)
                risk_r = round(abs(entry - sl), 2)
                if risk_r <= 0: continue

                target1 = round(entry + 1.5 * risk_r, 2)
                target2 = round(entry + 2.5 * risk_r, 2)
                score = round(50 + (cand['rs'] * 10), 1)

                picks.append({
                    'symbol': display_symbol,
                    'ticker': ticker,
                    'direction': 'LONG',
                    'entry': entry,
                    'sl': sl,
                    'target1': target1,
                    'target2': target2,
                    'risk_r': risk_r,
                    'adx': round(cand['rs'], 2),
                    'volume_ratio': 1.5,
                    'or_high': entry,
                    'or_low': sl,
                    'vwap': round(vwap_val, 2),
                    'score': score,
                    'timestamp': str(dt),
                    'breakout_time': dt.strftime('%H:%M')
                })
                break

    picks.sort(key=lambda x: x['score'], reverse=True)
    max_picks = getattr(config, 'MAX_PICKS_PER_RUN', 5)
    return picks[:max_picks]

if __name__ == '__main__':
    print('RS Momentum Screener with Regime Filter loaded.')
