"""
Fix Return_Pct calculation in export_1year_trades.py
Stores return as decimal (e.g. 0.015 for +1.50%, -0.01 for -1.00%)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def export_1year_trade_log():
    symbols = load_watchlist()[:100]
    all_tickers = symbols + ['^NSEI']
    print("=== RE-EXPORTING 1-YEAR TRADE LOG (FIXED RETURN %) ===")

    df_intraday = yf.download(all_tickers, period="365d", interval="60m", progress=False, group_by="ticker")
    df_daily = yf.download(['^NSEI'], period="500d", interval="1d", progress=False)

    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = df_daily.columns.get_level_values(0)
    df_daily.index = df_daily.index.tz_localize(None) if df_daily.index.tz is not None else df_daily.index

    df_daily['Nifty_EMA20'] = df_daily['Close'].ewm(span=20, adjust=False).mean()
    df_daily['Nifty_EMA50'] = df_daily['Close'].ewm(span=50, adjust=False).mean()

    nifty_intra = df_intraday['^NSEI'].dropna()
    nifty_intra.index = nifty_intra.index.tz_localize(None) if nifty_intra.index.tz is not None else nifty_intra.index

    capital = 100000.0
    running_capital = capital
    trades = []

    trading_dates = sorted(list(set(nifty_intra.index.date)))

    for t_date in trading_dates:
        prior_daily = df_daily[df_daily.index < pd.Timestamp(t_date)]
        if prior_daily.empty: continue
        last_d = prior_daily.iloc[-1]

        if last_d['Nifty_EMA20'] <= last_d['Nifty_EMA50']:
            continue

        nifty_day = nifty_intra[nifty_intra.index.date == t_date]
        if len(nifty_day) < 2: continue

        nifty_open = nifty_day.iloc[0]['Open']
        nifty_first = nifty_day.iloc[0]['Close']
        nifty_ret = (nifty_first - nifty_open) / nifty_open * 100.0

        stock_rs = []

        for symbol in symbols:
            try:
                s_df = df_intraday[symbol].dropna() if isinstance(df_intraday.columns, pd.MultiIndex) else df_intraday
                s_df.index = s_df.index.tz_localize(None) if s_df.index.tz is not None else s_df.index
                s_day = s_df[s_df.index.date == t_date]
                if len(s_day) < 2: continue

                s_open = s_day.iloc[0]['Open']
                s_first = s_day.iloc[0]['Close']
                s_ret = (s_first - s_open) / s_open * 100.0
                rs = s_ret - nifty_ret

                if rs > 1.0:
                    stock_rs.append({'symbol': symbol, 'rs': rs})
            except Exception:
                continue

        if not stock_rs: continue

        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_symbols = [x['symbol'] for x in stock_rs[:3]]

        for sym in top_rs_symbols:
            try:
                s_df = df_intraday[sym].dropna() if isinstance(df_intraday.columns, pd.MultiIndex) else df_intraday
                s_df.index = s_df.index.tz_localize(None) if s_df.index.tz is not None else s_df.index
                s_day = s_df[s_df.index.date == t_date]
                if len(s_day) < 3: continue

                s_day['EMA20'] = s_day['Close'].ewm(span=20, adjust=False).mean()
                session = s_day.iloc[1:]

                for dt, row in session.iterrows():
                    close, high, low = row['Close'], row['High'], row['Low']
                    ema20 = row['EMA20']

                    if close > ema20:
                        entry = close
                        sl = entry * 0.992
                        risk_r = entry - sl
                        t1 = entry + 1.5 * risk_r
                        t2 = entry + 2.5 * risk_r

                        pos_size = int((running_capital * 0.01) / risk_r)
                        if pos_size <= 0: break

                        rem = s_day.loc[dt:]
                        outcome = 'EXPIRED'
                        exit_price = rem.iloc[-1]['Close']
                        trail_sl = sl

                        for r_dt, r_row in rem.iloc[1:].iterrows():
                            r_h, r_l = r_row['High'], r_row['Low']
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

                        pnl = (exit_price - entry) * pos_size
                        # Store return as ratio (e.g. 0.015 for +1.50%)
                        ret_ratio = pnl / running_capital
                        running_capital += pnl

                        trades.append({
                            'Date': str(t_date),
                            'Symbol': sym.replace('.NS', ''),
                            'Direction': 'LONG',
                            'Entry_Price': round(entry, 2),
                            'Exit_Price': round(exit_price, 2),
                            'SL_Price': round(sl, 2),
                            'Shares': pos_size,
                            'Outcome': outcome,
                            'PnL_Rs': round(pnl, 2),
                            'Return_Pct': round(ret_ratio, 6),
                            'Capital_After': round(running_capital, 2)
                        })
                        break
            except Exception:
                continue

    df_export = pd.DataFrame(trades)
    csv_path = "1year_trades_log.csv"
    df_export.to_csv(csv_path, index=False)
    print(f"Exported {len(df_export)} trades to {csv_path} with fixed Return decimal format.")

if __name__ == '__main__':
    export_1year_trade_log()
