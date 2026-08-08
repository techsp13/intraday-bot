"""
Detailed 30-Day Backtest Report: NIFTY Relative Strength (RS) Momentum Strategy
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def run_detailed_rs_report():
    symbols = load_watchlist()[:100]
    all_tickers = symbols + ['^NSEI']
    print(f"=== 30-DAY BACKTEST REPORT: NIFTY RELATIVE STRENGTH (RS) MOMENTUM ===")
    print("Downloading 30-day market data...")
    df_15m = yf.download(all_tickers, period="30d", interval="15m", progress=False, group_by="ticker")
    df_5m = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")

    nifty_15m = df_15m['^NSEI'].dropna()
    nifty_15m.index = nifty_15m.index.tz_localize(None) if nifty_15m.index.tz is not None else nifty_15m.index

    capital = 100000.0
    initial_cap = capital
    trades = []
    daily_pnls = {}

    trading_dates = sorted(list(set(nifty_15m.index.date)))

    for t_date in trading_dates:
        nifty_day = nifty_15m[nifty_15m.index.date == t_date]
        if len(nifty_day) < 4: continue

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
                rs = s_ret - nifty_ret

                if rs > 1.2:
                    stock_rs.append({'symbol': symbol, 'rs': rs})
            except Exception:
                continue

        if not stock_rs: continue

        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_symbols = [x['symbol'] for x in stock_rs[:3]]

        day_pnl = 0.0

        for sym in top_rs_symbols:
            try:
                s_5m = df_5m[sym].dropna() if isinstance(df_5m.columns, pd.MultiIndex) else df_5m
                s_5m.index = s_5m.index.tz_localize(None) if s_5m.index.tz is not None else s_5m.index
                s_5m_day = s_5m[s_5m.index.date == t_date]
                if len(s_5m_day) < 10: continue

                s_5m_day['EMA20'] = s_5m_day['Close'].ewm(span=20, adjust=False).mean()
                s_5m_day['EMA50'] = s_5m_day['Close'].ewm(span=50, adjust=False).mean()

                session = s_5m_day.between_time('09:45', '14:00')

                for dt, row in session.iterrows():
                    close, high, low = row['Close'], row['High'], row['Low']
                    ema20, ema50 = row['EMA20'], row['EMA50']

                    if ema20 > ema50 and abs(low - ema20)/ema20 <= 0.004 and close > ema20:
                        entry = close
                        sl = entry * 0.992
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
                        day_pnl += pnl

                        trades.append({
                            'date': str(t_date),
                            'symbol': sym.replace('.NS', ''),
                            'entry': entry,
                            'sl': sl,
                            't1': t1,
                            'outcome': outcome,
                            'pnl': pnl,
                            'r_m': r_m
                        })
                        break
            except Exception:
                continue

        daily_pnls[str(t_date)] = day_pnl

    df_t = pd.DataFrame(trades)
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
    print("     DETAILED 30-DAY PERFORMANCE BREAKDOWN     ")
    print("="*60)
    print(f"Starting Capital:     Rs. {initial_cap:,.2f}")
    print(f"Ending Capital:       Rs. {initial_cap + net_pnl:,.2f}")
    print(f"NET PROFIT / LOSS:    Rs. {net_pnl:+,.2f} ({net_pnl/initial_cap*100:+.2f}%)")
    print(f"Profit Factor:        {profit_factor:.2f}")
    print(f"Average R-Multiple:   {df_t['r_m'].mean():+.2f}R")
    print("-" * 60)
    print(f"Total Trades Taken:   {total_trades}")
    print(f"Target Hits (Wins):   {wins} ({(wins/total_trades*100):.1f}%)")
    print(f"Breakeven Exits:      {be} ({(be/total_trades*100):.1f}%)")
    print(f"Stop Loss Hits:       {losses} ({(losses/total_trades*100):.1f}%)")
    print(f"Expired Exits:        {exp} ({(exp/total_trades*100):.1f}%)")
    print("="*60)

    print("\nDAILY P&L BREAKDOWN (LAST 10 TRADING DAYS):")
    print("-" * 60)
    for d, pnl in list(daily_pnls.items())[-10:]:
        status = "[PROFIT]" if pnl >= 0 else "[LOSS]"
        print(f"{d}  |  {status:<8}:  Rs. {pnl:+,.2f}")

    print("\nSAMPLE RECENT TRADES:")
    print("-" * 60)
    for idx, row in df_t.tail(8).iterrows():
        print(f"{row['date']} | {row['symbol']:<12} | Entry: Rs. {row['entry']:<8.2f} | Outcome: {row['outcome']:<10} | P&L: Rs. {row['pnl']:+,.2f}")

if __name__ == '__main__':
    run_detailed_rs_report()
