"""
6-Month (180-Day) Historical Backtest: NIFTY Relative Strength (RS) Momentum Strategy
Uses 60-minute candles to backtest across the full 6-month historical window.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def run_6month_rs_report():
    symbols = load_watchlist()[:100]
    all_tickers = symbols + ['^NSEI']
    print(f"=== 6-MONTH (180-DAY) HISTORICAL BACKTEST: NIFTY RELATIVE STRENGTH ===")
    print("Downloading 180-day 60m data from Yahoo Finance...")
    df_60m = yf.download(all_tickers, period="180d", interval="60m", progress=False, group_by="ticker")
    df_daily = yf.download(all_tickers, period="240d", interval="1d", progress=False, group_by="ticker")

    if '^NSEI' not in df_60m.columns.levels[0]:
        print("Nifty index data missing")
        return

    nifty_60m = df_60m['^NSEI'].dropna()
    nifty_60m.index = nifty_60m.index.tz_localize(None) if nifty_60m.index.tz is not None else nifty_60m.index

    capital = 100000.0
    initial_cap = capital
    trades = []
    daily_pnls = {}

    trading_dates = sorted(list(set(nifty_60m.index.date)))

    for t_date in trading_dates:
        nifty_day = nifty_60m[nifty_60m.index.date == t_date]
        if len(nifty_day) < 2: continue

        nifty_open = nifty_day.iloc[0]['Open']
        nifty_first_hr = nifty_day.iloc[0]['Close']
        nifty_ret = (nifty_first_hr - nifty_open) / nifty_open * 100.0

        stock_rs = []

        for symbol in symbols:
            try:
                s_60m = df_60m[symbol].dropna() if isinstance(df_60m.columns, pd.MultiIndex) else df_60m
                s_60m.index = s_60m.index.tz_localize(None) if s_60m.index.tz is not None else s_60m.index
                s_day = s_60m[s_60m.index.date == t_date]
                if len(s_day) < 2: continue

                s_open = s_day.iloc[0]['Open']
                s_first_hr = s_day.iloc[0]['Close']
                s_ret = (s_first_hr - s_open) / s_open * 100.0
                rs = s_ret - nifty_ret

                if rs > 1.0:
                    stock_rs.append({'symbol': symbol, 'rs': rs})
            except Exception:
                continue

        if not stock_rs: continue

        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_symbols = [x['symbol'] for x in stock_rs[:3]]

        day_pnl = 0.0

        for sym in top_rs_symbols:
            try:
                s_day = df_60m[sym].dropna() if isinstance(df_60m.columns, pd.MultiIndex) else df_60m
                s_day.index = s_day.index.tz_localize(None) if s_day.index.tz is not None else s_day.index
                s_60m_day = s_day[s_day.index.date == t_date]
                if len(s_60m_day) < 3: continue

                s_60m_day['EMA20'] = s_60m_day['Close'].ewm(span=20, adjust=False).mean()

                session = s_60m_day.iloc[1:]  # After 1st hour

                for dt, row in session.iterrows():
                    close, high, low = row['Close'], row['High'], row['Low']
                    ema20 = row['EMA20']

                    if close > ema20:
                        entry = close
                        sl = entry * 0.99
                        risk_r = entry - sl
                        t1 = entry + 1.5 * risk_r
                        t2 = entry + 2.5 * risk_r

                        pos_size = int((capital * 0.01) / risk_r)
                        if pos_size <= 0: break

                        rem = s_60m_day.loc[dt:]
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
                        day_pnl += pnl

                        trades.append({
                            'date': str(t_date),
                            'symbol': sym.replace('.NS', ''),
                            'outcome': outcome,
                            'pnl': pnl,
                            'r_m': r_m
                        })
                        break
            except Exception:
                continue

        daily_pnls[str(t_date)] = day_pnl

    df_t = pd.DataFrame(trades)
    if df_t.empty:
        print("No trades triggered in 180d window.")
        return

    total_trades = len(df_t)
    wins = len(df_t[df_t['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    be = len(df_t[df_t['outcome'] == 'HIT_BE'])
    losses = len(df_t[df_t['outcome'] == 'HIT_SL'])
    exp = len(df_t[df_t['outcome'] == 'EXPIRED'])

    gross_profit = df_t[df_t['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df_t[df_t['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
    net_pnl = df_t['pnl'].sum()

    print("\n" + "="*60)
    print("     DETAILED 6-MONTH (180-DAY) PERFORMANCE BREAKDOWN     ")
    print("="*60)
    print(f"Starting Capital:     Rs. {initial_cap:,.2f}")
    print(f"Ending Capital:       Rs. {initial_cap + net_pnl:,.2f}")
    print(f"NET PROFIT / LOSS:    Rs. {net_pnl:+,.2f} ({net_pnl/initial_cap*100:+.2f}%)")
    print(f"Profit Factor:        {profit_factor:.2f}")
    print(f"Average R-Multiple:   {df_t['r_m'].mean():+.2f}R")
    print("-" * 60)
    print(f"Total Trades Taken:   {total_trades} across {len(daily_pnls)} trading days")
    print(f"Target Hits (Wins):   {wins} ({(wins/total_trades*100):.1f}%)")
    print(f"Breakeven Exits:      {be} ({(be/total_trades*100):.1f}%)")
    print(f"Stop Loss Hits:       {losses} ({(losses/total_trades*100):.1f}%)")
    print(f"Expired Exits:        {exp} ({(exp/total_trades*100):.1f}%)")
    print("="*60)

if __name__ == '__main__':
    run_6month_rs_report()
