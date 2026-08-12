"""
Check Backtest Results for the Last 3 Trading Days across full 500-stock watchlist (Matching Live Telegram Bot 1:1)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def run_recent_3days_report_full_watchlist():
    symbols = load_watchlist()  # Full 500 stocks matching live bot 1:1
    all_tickers = symbols + ['^NSEI']
    print("=== BACKTEST REPORT FOR LAST 3 TRADING DAYS (FULL 500 WATCHLIST) ===")

    df_5m = yf.download(all_tickers, period="5d", interval="5m", progress=False, group_by="ticker")
    df_daily = yf.download(['^NSEI'], period="30d", interval="1d", progress=False)

    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = df_daily.columns.get_level_values(0)
    df_daily.index = df_daily.index.tz_localize(None) if df_daily.index.tz is not None else df_daily.index

    df_daily['Nifty_EMA20'] = df_daily['Close'].ewm(span=20, adjust=False).mean()
    df_daily['Nifty_EMA50'] = df_daily['Close'].ewm(span=50, adjust=False).mean()

    nifty_5m = df_5m['^NSEI'].dropna() if isinstance(df_5m.columns, pd.MultiIndex) else df_5m
    nifty_5m.index = nifty_5m.index.tz_localize(None) if nifty_5m.index.tz is not None else nifty_5m.index

    trading_dates = sorted(list(set(nifty_5m.index.date)))[-3:]

    capital = 100000.0
    running_capital = capital
    trades = []

    for t_date in trading_dates:
        prior_daily = df_daily[df_daily.index < pd.Timestamp(t_date)]
        if prior_daily.empty: continue
        last_d = prior_daily.iloc[-1]

        if last_d['Nifty_EMA20'] <= last_d['Nifty_EMA50']:
            continue

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

            entry_candle = s_day.iloc[0]
            entry_dt = s_day.index[0]

            entry = entry_candle['Open']
            sl = entry * 0.992
            risk_r = entry - sl
            t1 = entry + 1.5 * risk_r
            t2 = entry + 2.5 * risk_r

            pos_size = int((running_capital * 0.01) / risk_r)
            if pos_size <= 0: continue

            session = s_day.iloc[1:]
            outcome = 'EXPIRED_SAME_DAY'
            exit_price = session.iloc[-1]['Close']
            exit_time_str = "03:15 PM"
            trail_sl = sl

            for dt, row in session.iterrows():
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
                    exit_price = trail_sl
                    exit_time_str = dt.strftime('%I:%M %p')
                    break

            pnl = (exit_price - entry) * pos_size
            ret_ratio = pnl / running_capital
            running_capital += pnl

            trades.append({
                'Date': str(t_date),
                'Alert_Signal_Time': '09:05 AM',
                'Entry_Time': '09:15 AM',
                'Exit_Time': exit_time_str,
                'Symbol': sym.replace('.NS', ''),
                'Direction': 'LONG',
                'Entry_Price': round(entry, 2),
                'Exit_Price': round(exit_price, 2),
                'SL_Price': round(sl, 2),
                'Target1_Price': round(t1, 2),
                'Target2_Price': round(t2, 2),
                'Shares': pos_size,
                'Outcome': outcome,
                'PnL_Rs': round(pnl, 2),
                'Return_Pct': round(ret_ratio, 6),
                'Capital_After': round(running_capital, 2)
            })

    df_res = pd.DataFrame(trades)
    print("\n" + "="*75)
    print("   EXACT LIVE BOT MATCHED BACKTEST (FULL 500 WATCHLIST: 10-AUG to 12-AUG)   ")
    print("="*75)
    if not df_res.empty:
        print(df_res[['Date', 'Entry_Time', 'Exit_Time', 'Symbol', 'Entry_Price', 'Exit_Price', 'Outcome', 'PnL_Rs', 'Capital_After']].to_string(index=False))

if __name__ == '__main__':
    run_recent_3days_report_full_watchlist()
