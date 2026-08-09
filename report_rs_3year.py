"""
3-Year (1095-Day) Historical Backtest: NIFTY Relative Strength Momentum Strategy
Evaluates performance across 2023, 2024, 2025, and 2026 daily market data.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist

def run_3year_rs_report():
    symbols = load_watchlist()[:100]
    all_tickers = symbols + ['^NSEI']
    print("=== 3-YEAR (1095-DAY) HISTORICAL BACKTEST: NIFTY RELATIVE STRENGTH ===")
    print("Downloading 3-year daily market data from Yahoo Finance...")

    df_daily = yf.download(all_tickers, period="3y", interval="1d", progress=False, group_by="ticker")

    if '^NSEI' not in df_daily.columns.levels[0]:
        print("Nifty index data missing")
        return

    nifty_df = df_daily['^NSEI'].dropna(subset=['Open', 'High', 'Low', 'Close'])
    nifty_df.index = nifty_df.index.tz_localize(None) if nifty_df.index.tz is not None else nifty_df.index

    # Calculate Nifty 20 EMA & 50 EMA for Market Regime Filter
    nifty_df['Nifty_EMA20'] = nifty_df['Close'].ewm(span=20, adjust=False).mean()
    nifty_df['Nifty_EMA50'] = nifty_df['Close'].ewm(span=50, adjust=False).mean()
    nifty_df['Nifty_5d_Ret'] = nifty_df['Close'].pct_change(5) * 100.0

    capital = 100000.0
    initial_cap = capital
    trades = []
    daily_pnls = {}
    paused_days = 0
    active_days = 0

    trading_dates = sorted(list(set(nifty_df.index.date)))[50:]  # Skip initial EMA warmup

    for t_date in trading_dates:
        t_ts = pd.Timestamp(t_date)
        if t_ts not in nifty_df.index: continue

        nifty_row = nifty_df.loc[t_ts]

        # ── MARKET REGIME FILTER: Pause buys when Nifty 20 EMA <= 50 EMA ──
        if nifty_row['Nifty_EMA20'] <= nifty_row['Nifty_EMA50']:
            paused_days += 1
            continue

        active_days += 1
        nifty_5d_ret = nifty_row['Nifty_5d_Ret']
        if pd.isna(nifty_5d_ret): continue

        stock_rs = []

        for symbol in symbols:
            try:
                s_df = df_daily[symbol].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(df_daily.columns, pd.MultiIndex) else df_daily
                s_df.index = s_df.index.tz_localize(None) if s_df.index.tz is not None else s_df.index

                if t_ts not in s_df.index: continue

                idx_loc = s_df.index.get_loc(t_ts)
                if idx_loc < 5: continue

                s_close = s_df.iloc[idx_loc]['Close']
                s_close_prev5 = s_df.iloc[idx_loc - 5]['Close']
                s_5d_ret = (s_close - s_close_prev5) / s_close_prev5 * 100.0

                rs = s_5d_ret - nifty_5d_ret  # Relative strength vs Nifty

                if rs > 2.0:  # RS Outperformance > 2.0%
                    stock_rs.append({'symbol': symbol, 'rs': rs, 'idx_loc': idx_loc, 's_df': s_df})
            except Exception:
                continue

        if not stock_rs: continue

        # Top 3 RS outperformers
        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_candidates = stock_rs[:3]

        day_pnl = 0.0

        for cand in top_rs_candidates:
            sym = cand['symbol']
            idx_loc = cand['idx_loc']
            s_df = cand['s_df']

            if idx_loc + 1 >= len(s_df): continue

            # Next day entry at Open
            next_row = s_df.iloc[idx_loc + 1]
            entry = next_row['Open']
            sl = entry * 0.98  # 2.0% Stop Loss
            risk_r = entry - sl
            t1 = entry + 1.5 * risk_r  # +3.0% Target 1
            t2 = entry + 2.5 * risk_r  # +5.0% Target 2

            pos_size = int((capital * 0.01) / risk_r)
            if pos_size <= 0: continue

            # Simulate holding trade up to 5 days
            future_candles = s_df.iloc[idx_loc + 1 : idx_loc + 6]
            outcome = 'EXPIRED'
            exit_price = future_candles.iloc[-1]['Close']
            trail_sl = sl

            for f_idx, f_row in future_candles.iterrows():
                f_high = f_row['High']
                f_low = f_row['Low']

                # Trailing SL to breakeven at +1.0R
                if f_high >= (entry + 1.0 * risk_r):
                    trail_sl = max(trail_sl, entry)

                if f_high >= t1:
                    outcome = 'HIT_T1'
                    exit_price = t1
                    if f_high >= t2:
                        outcome = 'HIT_T2'
                        exit_price = t2
                    break
                elif f_low <= trail_sl:
                    outcome = 'HIT_SL' if trail_sl < entry else 'HIT_BE'
                    exit_price = trail_sl
                    break

            pnl = (exit_price - entry) * pos_size
            r_m = pnl / (risk_r * pos_size) if (risk_r * pos_size) > 0 else 0.0
            day_pnl += pnl

            trades.append({
                'date': str(t_date),
                'symbol': sym.replace('.NS', ''),
                'outcome': outcome,
                'pnl': pnl,
                'r_m': r_m
            })

        daily_pnls[str(t_date)] = day_pnl

    df_t = pd.DataFrame(trades)
    if df_t.empty:
        print("No trades triggered in 3-year window.")
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
    print("     DETAILED 3-YEAR (1095-DAY) PERFORMANCE BREAKDOWN     ")
    print("="*60)
    print(f"Starting Capital:     Rs. {initial_cap:,.2f}")
    print(f"Ending Capital:       Rs. {initial_cap + net_pnl:,.2f}")
    print(f"NET PROFIT / LOSS:    Rs. {net_pnl:+,.2f} ({net_pnl/initial_cap*100:+.2f}%)")
    print(f"Profit Factor:        {profit_factor:.2f}")
    print(f"Average R-Multiple:   {df_t['r_m'].mean():+.2f}R")
    print("-" * 60)
    print(f"Total Trading Days:   {len(trading_dates)} (Active: {active_days}, Paused: {paused_days})")
    print(f"Total Trades Taken:   {total_trades}")
    print(f"Target Hits (Wins):   {wins} ({(wins/total_trades*100):.1f}%)")
    print(f"Breakeven Exits:      {be} ({(be/total_trades*100):.1f}%)")
    print(f"Stop Loss Hits:       {losses} ({(losses/total_trades*100):.1f}%)")
    print(f"Expired Exits:        {exp} ({(exp/total_trades*100):.1f}%)")
    print("="*60)

if __name__ == '__main__':
    run_3year_rs_report()
