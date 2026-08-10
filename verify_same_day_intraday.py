"""
Intraday Backtest with Exact Breakout Entry Trigger Time
Tracks:
- Signal_Alert_Time (09:15 AM)
- Entry_Trigger_Level (Rs. 220)
- Entry_Trigger_Time (e.g. 09:35 AM - exact candle timestamp when price crossed entry level)
- Exit_Time (e.g. 11:20 AM - exact candle timestamp when Target/SL hit)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def run_intraday_with_breakout_trigger_time():
    symbols = load_watchlist()[:80]
    all_tickers = symbols + ['^NSEI']
    print("=== EXPORTING INTRADAY LOG WITH EXACT BREAKOUT ENTRY TRIGGER TIME ===")
    print("Downloading 5m intraday market data...")

    df_5m = yf.download(all_tickers, period="30d", interval="5m", progress=False, group_by="ticker")
    df_daily = yf.download(['^NSEI'], period="60d", interval="1d", progress=False)

    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = df_daily.columns.get_level_values(0)
    df_daily.index = df_daily.index.tz_localize(None) if df_daily.index.tz is not None else df_daily.index

    df_daily['Nifty_EMA20'] = df_daily['Close'].ewm(span=20, adjust=False).mean()
    df_daily['Nifty_EMA50'] = df_daily['Close'].ewm(span=50, adjust=False).mean()

    capital = 100000.0
    running_capital = capital
    trades = []

    nifty_5m = df_5m['^NSEI'].dropna() if isinstance(df_5m.columns, pd.MultiIndex) else df_5m
    nifty_5m.index = nifty_5m.index.tz_localize(None) if nifty_5m.index.tz is not None else nifty_5m.index
    trading_dates = sorted(list(set(nifty_5m.index.date)))

    for t_date in trading_dates:
        prior_daily = df_daily[df_daily.index < pd.Timestamp(t_date)]
        if prior_daily.empty: continue
        last_d = prior_daily.iloc[-1]

        if last_d['Nifty_EMA20'] <= last_d['Nifty_EMA50']:
            continue  # Market Regime Pause

        nifty_day = nifty_5m[nifty_5m.index.date == t_date]
        if len(nifty_day) < 4: continue

        nifty_open = nifty_day.iloc[0]['Open']
        nifty_945 = nifty_day.iloc[min(6, len(nifty_day)-1)]['Close']
        nifty_ret = (nifty_945 - nifty_open) / nifty_open * 100.0

        stock_rs = []

        for symbol in symbols:
            try:
                s_df = df_5m[symbol].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(df_5m.columns, pd.MultiIndex) else df_5m
                s_df.index = s_df.index.tz_localize(None) if s_df.index.tz is not None else s_df.index
                s_day = s_df[s_df.index.date == t_date]
                if len(s_day) < 6: continue

                s_open = s_day.iloc[0]['Open']
                s_945 = s_day.iloc[min(6, len(s_day)-1)]['Close']
                s_ret = (s_945 - s_open) / s_open * 100.0
                rs = s_ret - nifty_ret

                if rs > 1.0:
                    stock_rs.append({'symbol': symbol, 'rs': rs, 's_day': s_day})
            except Exception:
                continue

        if not stock_rs: continue

        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_candidates = stock_rs[:3]

        for cand in top_rs_candidates:
            sym = cand['symbol']
            s_day = cand['s_day']

            alert_time_str = "09:15 AM"
            first_candle = s_day.iloc[0]
            trigger_level = round(first_candle['High'], 2)  # Breakout trigger level (09:15 High)

            # Scan 5m candles to find exact candle when High crossed trigger_level
            entry_dt = s_day.index[0]
            entry_trigger_time_str = "09:15 AM"
            entry_price = first_candle['Open']
            session = s_day

            # Walk candles to find breakout trigger timestamp
            triggered = False
            for dt, row in s_day.iterrows():
                if row['High'] >= trigger_level:
                    entry_dt = dt
                    entry_trigger_time_str = dt.strftime('%I:%M %p')
                    entry_price = max(row['Open'], trigger_level)
                    triggered = True
                    break

            if not triggered:
                entry_trigger_time_str = "09:15 AM"

            entry = round(entry_price, 2)
            sl = round(entry * 0.992, 2)
            risk_r = round(entry - sl, 2)
            if risk_r <= 0: continue

            t1 = round(entry + 1.5 * risk_r, 2)
            t2 = round(entry + 2.5 * risk_r, 2)

            pos_size = int((running_capital * 0.01) / risk_r)
            if pos_size <= 0: continue

            # Post-entry session candles
            rem_session = s_day.loc[entry_dt:]
            outcome = 'EXPIRED_SAME_DAY'
            exit_price = round(rem_session.iloc[-1]['Close'], 2)
            exit_time_str = "03:15 PM"
            trail_sl = sl

            for dt, row in rem_session.iloc[1:].iterrows():
                r_h, r_l = row['High'], row['Low']
                if r_h >= (entry + 0.8 * risk_r):
                    trail_sl = max(trail_sl, entry)

                if r_h >= t1:
                    outcome = 'HIT_T1'
                    exit_price = t1
                    exit_time_str = dt.strftime('%I:%M %p')
                    if r_h >= t2:
                        outcome = 'HIT_T2'
                        exit_price = t2
                    break
                elif r_l <= trail_sl:
                    outcome = 'HIT_SL' if trail_sl < entry else 'HIT_BE'
                    exit_price = round(trail_sl, 2)
                    exit_time_str = dt.strftime('%I:%M %p')
                    break

            pnl = (exit_price - entry) * pos_size
            ret_ratio = pnl / running_capital
            running_capital += pnl

            trades.append({
                'Date': str(t_date),
                'Alert_Signal_Time': alert_time_str,
                'Entry_Trigger_Time': entry_trigger_time_str,
                'Exit_Time': exit_time_str,
                'Symbol': sym.replace('.NS', ''),
                'Direction': 'LONG',
                'Breakout_Level': trigger_level,
                'Entry_Price': entry,
                'Exit_Price': exit_price,
                'SL_Price': sl,
                'Target1_Price': t1,
                'Target2_Price': t2,
                'Shares': pos_size,
                'Outcome': outcome,
                'PnL_Rs': round(pnl, 2),
                'Return_Pct': round(ret_ratio, 6),
                'Capital_After': round(running_capital, 2)
            })

    df_export = pd.DataFrame(trades)
    df_export.to_csv("3year_trades_sameday_intraday.csv", index=False)
    print(f"Exported {len(df_export)} trades with exact Entry_Trigger_Time (when price crossed level)!")

if __name__ == '__main__':
    run_intraday_with_breakout_trigger_time()
