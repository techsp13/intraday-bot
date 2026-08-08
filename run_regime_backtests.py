"""
Comparative Multi-Period Backtest with Market Regime Filter (1M, 2M, 6M)
Strategy: NIFTY Relative Strength Outperformance + Market Regime Filter (Nifty 20 EMA > 50 EMA)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def run_regime_backtest_for_period(symbols, period_str, interval_str):
    all_tickers = symbols + ['^NSEI']
    df_intraday = yf.download(all_tickers, period=period_str, interval=interval_str, progress=False, group_by="ticker")
    df_daily = yf.download(['^NSEI'], period="365d", interval="1d", progress=False)

    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = df_daily.columns.get_level_values(0)
    df_daily.index = df_daily.index.tz_localize(None) if df_daily.index.tz is not None else df_daily.index

    df_daily['Nifty_EMA20'] = df_daily['Close'].ewm(span=20, adjust=False).mean()
    df_daily['Nifty_EMA50'] = df_daily['Close'].ewm(span=50, adjust=False).mean()

    nifty_intra = df_intraday['^NSEI'].dropna()
    nifty_intra.index = nifty_intra.index.tz_localize(None) if nifty_intra.index.tz is not None else nifty_intra.index

    capital = 100000.0
    initial_cap = capital
    trades = []
    paused_days = 0
    active_days = 0

    trading_dates = sorted(list(set(nifty_intra.index.date)))

    for t_date in trading_dates:
        # REGIME FILTER CHECK
        prior_daily = df_daily[df_daily.index < pd.Timestamp(t_date)]
        if prior_daily.empty: continue
        last_d = prior_daily.iloc[-1]

        # If Nifty Daily 20 EMA <= 50 EMA, MARKET IS IN CORRECTION -> PAUSE BUYS
        if last_d['Nifty_EMA20'] <= last_d['Nifty_EMA50']:
            paused_days += 1
            continue

        active_days += 1
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
                s_day['EMA50'] = s_day['Close'].ewm(span=50, adjust=False).mean()

                session = s_day.iloc[1:]

                for dt, row in session.iterrows():
                    close, high, low = row['Close'], row['High'], row['Low']
                    ema20, ema50 = row['EMA20'], row['EMA50']

                    if close > ema20:
                        entry = close
                        sl = entry * 0.992
                        risk_r = entry - sl
                        t1 = entry + 1.5 * risk_r
                        t2 = entry + 2.5 * risk_r

                        pos_size = int((capital * 0.01) / risk_r)
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
                        r_m = pnl / (risk_r * pos_size)
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

    df_t = pd.DataFrame(trades)
    if df_t.empty:
        return {'net_pnl': 0, 'return_pct': 0, 'trades': 0, 'win_rate': 0, 'pf': 0, 'paused': paused_days, 'active': active_days}

    total = len(df_t)
    wins = len(df_t[df_t['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    losses = len(df_t[df_t['outcome'] == 'HIT_SL'])
    gross_p = df_t[df_t['pnl'] > 0]['pnl'].sum()
    gross_l = abs(df_t[df_t['pnl'] < 0]['pnl'].sum())
    pf = gross_p / gross_l if gross_l > 0 else np.nan
    net_pnl = df_t['pnl'].sum()

    return {
        'net_pnl': net_pnl,
        'return_pct': (net_pnl / capital) * 100.0,
        'trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': (wins / total * 100) if total > 0 else 0,
        'pf': pf,
        'paused_days': paused_days,
        'active_days': active_days
    }

def main():
    symbols = load_watchlist()[:100]
    print("=============================================================")
    print("  RUNNING MULTI-PERIOD BACKTEST WITH MARKET REGIME FILTER    ")
    print("=============================================================")
    
    print("\n[1/3] Running 30-Day (1 Month) Backtest...")
    m1 = run_regime_backtest_for_period(symbols, "30d", "5m")
    
    print("\n[2/3] Running 60-Day (2 Months) Backtest...")
    m2 = run_regime_backtest_for_period(symbols, "60d", "5m")
    
    print("\n[3/3] Running 180-Day (6 Months) Backtest...")
    m6 = run_regime_backtest_for_period(symbols, "180d", "60m")

    print("\n" + "="*70)
    print("     FINAL COMPARATIVE SUMMARY (WITH MARKET REGIME FILTER)     ")
    print("="*70)
    print(f"{'Time Window':<18} | {'Net P&L (Rs.)':<14} | {'Return (%)':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Profit Factor':<12}")
    print("-" * 70)
    print(f"{'1 Month (30 Days)':<18} | Rs. {m1['net_pnl']:+<10,.2f} | {m1['return_pct']:+<8.2f}% | {m1['trades']:<8} | {m1['win_rate']:<8.1f}% | {m1['pf']:<10.2f}")
    print(f"{'2 Months (60 Days)':<18} | Rs. {m2['net_pnl']:+<10,.2f} | {m2['return_pct']:+<8.2f}% | {m2['trades']:<8} | {m2['win_rate']:<8.1f}% | {m2['pf']:<10.2f}")
    print(f"{'6 Months (180 Days)':<18} | Rs. {m6['net_pnl']:+<10,.2f} | {m6['return_pct']:+<8.2f}% | {m6['trades']:<8} | {m6['win_rate']:<8.1f}% | {m6['pf']:<10.2f}")
    print("="*70)

if __name__ == '__main__':
    main()
