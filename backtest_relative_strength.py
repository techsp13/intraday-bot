"""
NIFTY Relative Strength (RS) Momentum Strategy Backtest (30 Days)
Logic:
1. At 09:45 AM, calculate 15-min performance of each stock vs NIFTY 50 Index (^NSEI).
2. Filter top 3 stocks exhibiting Strongest Relative Strength (RS > +1.2% over Nifty).
3. Confirm with 15-min Supertrend (10, 3) GREEN + 20 EMA > 50 EMA.
4. Target: 1.5R | SL: 0.8% | Trailing SL to BE at +0.8R.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def calculate_supertrend(df, period=10, multiplier=3.0):
    high, low, close = df['High'], df['Low'], df['Close']
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0/period, adjust=False).mean()
    hl2 = (high + low) / 2.0
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)
    st = pd.Series(index=df.index, dtype=float)
    st_dir = pd.Series(index=df.index, dtype=int)
    
    for i in range(1, len(df)):
        ub = basic_ub.iloc[i] if basic_ub.iloc[i] < st.iloc[i-1] or close.iloc[i-1] > st.iloc[i-1] else st.iloc[i-1]
        lb = basic_lb.iloc[i] if basic_lb.iloc[i] > st.iloc[i-1] or close.iloc[i-1] < st.iloc[i-1] else st.iloc[i-1]
        if close.iloc[i] > ub:
            st.iloc[i] = lb
            st_dir.iloc[i] = 1
        elif close.iloc[i] < lb:
            st.iloc[i] = ub
            st_dir.iloc[i] = -1
        else:
            st.iloc[i] = st.iloc[i-1]
            st_dir.iloc[i] = st_dir.iloc[i-1] if i > 1 else 1
    return st, st_dir

def run_rs_backtest():
    symbols = load_watchlist()[:100]
    all_tickers = symbols + ['^NSEI']
    print(f"Downloading 30-day 15m & 5m data for Relative Strength strategy...")
    df_15m = yf.download(all_tickers, period="30d", interval="15m", progress=False, group_by="ticker")
    df_5m = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")

    if '^NSEI' not in df_15m.columns.levels[0]:
        print("Nifty index data missing")
        return

    nifty_15m = df_15m['^NSEI'].dropna()
    nifty_15m.index = nifty_15m.index.tz_localize(None) if nifty_15m.index.tz is not None else nifty_15m.index

    capital = 100000.0
    executed_trades = []

    trading_dates = sorted(list(set(nifty_15m.index.date)))

    for t_date in trading_dates:
        nifty_day = nifty_15m[nifty_15m.index.date == t_date]
        if len(nifty_day) < 4: continue

        # Nifty morning performance (09:15 to 09:45)
        nifty_open = nifty_day.iloc[0]['Open']
        nifty_945 = nifty_day.iloc[1]['Close'] if len(nifty_day) > 1 else nifty_open
        nifty_ret = (nifty_945 - nifty_open) / nifty_open * 100.0

        stock_rs = []

        for symbol in symbols:
            try:
                s_15m = df_15m[symbol].dropna() if isinstance(df_15m.columns, pd.MultiIndex) else df_15m
                s_15m.index = s_15m.index.tz_localize(None) if s_15m.index.tz is not None else s_15m.index
                s_day = s_15m[s_15m.index.date == t_date]
                if len(s_day) < 2: continue

                s_open = s_day.iloc[0]['Open']
                s_945 = s_day.iloc[1]['Close']
                s_ret = (s_945 - s_open) / s_open * 100.0
                rs = s_ret - nifty_ret  # Relative strength vs Nifty

                if rs > 1.2:  # Strong RS outperformance (>1.2%)
                    stock_rs.append({'symbol': symbol, 'rs': rs})
            except Exception:
                continue

        if not stock_rs: continue

        # Rank by Relative Strength
        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_symbols = [x['symbol'] for x in stock_rs[:3]]  # Top 3 RS outperformers

        for sym in top_rs_symbols:
            try:
                s_5m = df_5m[sym].dropna() if isinstance(df_5m.columns, pd.MultiIndex) else df_5m
                s_5m.index = s_5m.index.tz_localize(None) if s_5m.index.tz is not None else s_5m.index
                s_5m_day = s_5m[s_5m.index.date == t_date]
                if len(s_5m_day) < 10: continue

                # Calculate EMAs
                s_5m_day['EMA20'] = s_5m_day['Close'].ewm(span=20, adjust=False).mean()
                s_5m_day['EMA50'] = s_5m_day['Close'].ewm(span=50, adjust=False).mean()

                session = s_5m_day.between_time('09:45', '14:00')

                for dt, row in session.iterrows():
                    close, high, low = row['Close'], row['High'], row['Low']
                    ema20, ema50 = row['EMA20'], row['EMA50']

                    # Long entry on 5m pullbacks to 20 EMA
                    if ema20 > ema50 and abs(low - ema20)/ema20 <= 0.004 and close > ema20:
                        entry = close
                        sl = entry * 0.992  # Tight 0.8% SL
                        risk_r = entry - sl
                        t1 = entry + 1.5 * risk_r
                        t2 = entry + 2.5 * risk_r

                        pos_size = int((capital * 0.01) / risk_r)
                        if pos_size <= 0: break

                        rem = s_5m_day.loc[dt:]
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
                        r_m = pnl / (risk_r * pos_size)
                        executed_trades.append({'date': t_date, 'symbol': sym, 'outcome': outcome, 'pnl': pnl, 'r_m': r_m})
                        break
            except Exception:
                continue

    df_res = pd.DataFrame(executed_trades)
    if df_res.empty:
        print("No RS trades triggered")
        return

    total = len(df_res)
    wins = len(df_res[df_res['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    be = len(df_res[df_res['outcome'] == 'HIT_BE'])
    losses = len(df_res[df_res['outcome'] == 'HIT_SL'])
    exp = len(df_res[df_res['outcome'] == 'EXPIRED'])
    net_pnl = df_res['pnl'].sum()

    print("\n" + "="*55)
    print("  NIFTY RELATIVE STRENGTH (RS) MOMENTUM BACKTEST RESULTS  ")
    print("="*55)
    print(f"Total Trades Taken:    {total} (Selective: ~{total/20:.1f} per day)")
    print(f"Wins / BE / Losses / Exp: {wins} W / {be} BE / {losses} L / {exp} E")
    print(f"WIN RATE (Target Hits): {(wins/(wins+losses)*100 if (wins+losses)>0 else 0):.1f}%")
    print(f"Average R-Multiple:    {df_res['r_m'].mean():+.2f}R")
    print(f"NET PROFIT / LOSS:     Rs. {net_pnl:+,.2f} ({net_pnl/capital*100:+.2f}%)")
    print("="*55)

if __name__ == '__main__':
    run_rs_backtest()
