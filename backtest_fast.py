"""
Fast Multi-Strategy Backtest Suite (30-Day Period)
Tests 3 robust intraday strategy variations across top NSE stocks.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist
from screener import calculate_adx, calculate_vwap, calculate_atr
from risk_manager import calculate_position_size

def run_multi_backtest():
    symbols = load_watchlist()[:80]
    print(f"Downloading 30-day 5m data for top {len(symbols)} liquid symbols...")
    df_5m_all = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")
    df_daily_all = yf.download(symbols, period="60d", interval="1d", progress=False, group_by="ticker")

    capital = 100000.0

    # ── Strategy 1: ORB 9:45 + Trailing Stop Loss to Breakeven ──
    s1_trades = []

    for symbol in symbols:
        try:
            df_5m = df_5m_all[symbol].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(df_5m_all.columns, pd.MultiIndex) else df_5m_all
            df_daily = df_daily_all[symbol].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(df_daily_all.columns, pd.MultiIndex) else df_daily_all

            if df_5m.empty or df_daily.empty: continue

            # Strip tz
            df_5m.index = df_5m.index.tz_localize(None) if df_5m.index.tz is not None else df_5m.index
            df_daily.index = df_daily.index.tz_localize(None) if df_daily.index.tz is not None else df_daily.index

            adx_df = calculate_adx(df_daily['High'], df_daily['Low'], df_daily['Close'])
            trading_dates = sorted(list(set(df_5m.index.date)))

            for t_date in trading_dates:
                day_df = df_5m[df_5m.index.date == t_date]
                if len(day_df) < 15: continue

                # Daily ADX filter (>20)
                prior_daily = df_daily[df_daily.index < pd.Timestamp(t_date)]
                if prior_daily.empty: continue
                last_dt = prior_daily.index[-1]
                adx_val = adx_df.loc[last_dt, 'adx'] if last_dt in adx_df.index else 0
                if pd.isna(adx_val) or adx_val < 20.0: continue

                # Opening Range (09:15 to 09:44)
                or_df = day_df.between_time('09:15', '09:44')
                if len(or_df) < 5: continue
                or_high, or_low = or_df['High'].max(), or_df['Low'].min()

                vwap = calculate_vwap(day_df)
                post_or = day_df.between_time('09:45', '14:30')

                for dt, row in post_or.iterrows():
                    close = row['Close']
                    high = row['High']
                    low = row['Low']
                    v_val = vwap.loc[dt]

                    direction = None
                    if close > or_high and close > v_val:
                        direction = 'LONG'
                        entry = close
                        sl = min(or_low, low)
                    elif close < or_low and close < v_val:
                        direction = 'SHORT'
                        entry = close
                        sl = max(or_high, high)

                    if direction:
                        risk_r = abs(entry - sl)
                        if risk_r <= 0 or (risk_r / entry) > 0.025: continue  # SL max 2.5%

                        t1 = entry + 1.5 * risk_r if direction == 'LONG' else entry - 1.5 * risk_r
                        t2 = entry + 2.5 * risk_r if direction == 'LONG' else entry - 2.5 * risk_r
                        pos_size = calculate_position_size(capital, entry, sl)
                        if pos_size <= 0: continue

                        rem = day_df.loc[dt:]
                        outcome = 'EXPIRED'
                        exit_price = rem.iloc[-1]['Close']
                        trail_sl = sl

                        for r_dt, r_row in rem.iloc[1:].iterrows():
                            r_h, r_l = r_row['High'], r_row['Low']
                            if direction == 'LONG':
                                # Trailing SL: move to breakeven once price reaches +0.8R
                                if r_h >= (entry + 0.8 * risk_r):
                                    trail_sl = max(trail_sl, entry)
                                if r_h >= t1:
                                    outcome = 'HIT_T1'
                                    exit_price = t1
                                    if r_h >= t2:
                                        outcome = 'HIT_T2'
                                        exit_price = t2
                                    break
                                elif r_l <= trail_sl:
                                    outcome = 'HIT_SL' if trail_sl < entry else 'HIT_BE'
                                    exit_price = trail_sl
                                    break
                            else: # SHORT
                                if r_l <= (entry - 0.8 * risk_r):
                                    trail_sl = min(trail_sl, entry)
                                if r_l <= t1:
                                    outcome = 'HIT_T1'
                                    exit_price = t1
                                    if r_l <= t2:
                                        outcome = 'HIT_T2'
                                        exit_price = t2
                                    break
                                elif r_h >= trail_sl:
                                    outcome = 'HIT_SL' if trail_sl > entry else 'HIT_BE'
                                    exit_price = trail_sl
                                    break

                        mult = 1 if direction == 'LONG' else -1
                        pnl = (exit_price - entry) * pos_size * mult
                        r_m = pnl / (risk_r * pos_size)
                        s1_trades.append({'date': t_date, 'symbol': symbol, 'pnl': pnl, 'outcome': outcome, 'r_m': r_m})
                        break

        except Exception as e:
            continue

    df1 = pd.DataFrame(s1_trades)
    if not df1.empty:
        total1 = len(df1)
        wins1 = len(df1[df1['outcome'].isin(['HIT_T1', 'HIT_T2'])])
        be1 = len(df1[df1['outcome'] == 'HIT_BE'])
        losses1 = len(df1[df1['outcome'] == 'HIT_SL'])
        pnl1 = df1['pnl'].sum()

        print("\n" + "="*55)
        print("  STRATEGY 1 RESULTS: ORB + TRAILING SL TO BREAKEVEN  ")
        print("="*55)
        print(f"Total Trades:         {total1}")
        print(f"Wins / BE / Losses:   {wins1} W / {be1} BE / {losses1} L")
        print(f"Win Rate (Target Hits): {(wins1/total1*100):.1f}%")
        print(f"Average R-Multiple:   {df1['r_m'].mean():+.2f}R")
        print(f"NET PROFIT / LOSS:    Rs. {pnl1:+,.2f} ({pnl1/capital*100:+.2f}%)")
        print("="*55)
    else:
        print("No S1 trades triggered.")

if __name__ == '__main__':
    run_multi_backtest()
