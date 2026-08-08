"""
CPR (Central Pivot Range) Narrow Width + VWAP Strategy Backtest (30 Days)
Logic:
1. Yesterday's CPR Width = |TC - BC| / Pivot * 100. Must be NARROW (< 0.35%)
2. Long Entry: 5m candle Close > TC AND Close > VWAP
3. Short Entry: 5m candle Close < BC AND Close < VWAP
4. Target: 1.5R or R1/S1 pivot level
5. Stop Loss: Opposite CPR boundary (or max 1.0%)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist
from screener import calculate_vwap

def run_cpr_backtest():
    symbols = load_watchlist()[:150]
    print(f"Running CPR Narrow Width + VWAP Backtest on top {len(symbols)} stocks...")

    intraday_batch = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")
    daily_batch = yf.download(symbols, period="60d", interval="1d", progress=False, group_by="ticker")

    trades = []
    capital = 100000.0

    for symbol in symbols:
        try:
            df_5m = intraday_batch[symbol].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(intraday_batch.columns, pd.MultiIndex) else intraday_batch
            df_daily = daily_batch[symbol].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(daily_batch.columns, pd.MultiIndex) else daily_batch

            if df_5m.empty or df_daily.empty or len(df_daily) < 10: continue

            df_5m.index = df_5m.index.tz_localize(None) if df_5m.index.tz is not None else df_5m.index
            df_daily.index = df_daily.index.tz_localize(None) if df_daily.index.tz is not None else df_daily.index

            trading_dates = sorted(list(set(df_5m.index.date)))

            for t_date in trading_dates:
                day_df = df_5m[df_5m.index.date == t_date].copy()
                if len(day_df) < 15: continue

                # Get YESTERDAY'S daily candle to compute CPR
                prior_daily = df_daily[df_daily.index < pd.Timestamp(t_date)]
                if prior_daily.empty: continue
                yest = prior_daily.iloc[-1]

                y_high, y_low, y_close = yest['High'], yest['Low'], yest['Close']
                pivot = (y_high + y_low + y_close) / 3.0
                bc = (y_high + y_low) / 2.0
                tc = (pivot - bc) + pivot

                # Ensure TC > BC
                if bc > tc: tc, bc = bc, tc

                cpr_width_pct = (tc - bc) / pivot * 100.0

                # FILTER 1: NARROW CPR ONLY (< 0.35% width)
                if cpr_width_pct > 0.35:
                    continue

                r1 = (2 * pivot) - y_low
                s1 = (2 * pivot) - y_high

                day_df['VWAP'] = calculate_vwap(day_df)
                session = day_df.between_time('09:30', '14:30')
                entered = False

                for dt, row in session.iterrows():
                    if entered: break
                    close, high, low = row['Close'], row['High'], row['Low']
                    vwap_val = row['VWAP']

                    direction = None
                    if close > tc and close > vwap_val:
                        direction = 'LONG'
                        entry = close
                        sl = max(bc, entry * 0.99)  # SL at BC line or 1%
                        target1 = r1 if r1 > entry else entry + 1.5 * (entry - sl)
                    elif close < bc and close < vwap_val:
                        direction = 'SHORT'
                        entry = close
                        sl = min(tc, entry * 1.01)  # SL at TC line or 1%
                        target1 = s1 if s1 < entry else entry - 1.5 * (sl - entry)

                    if direction:
                        risk_r = abs(entry - sl)
                        if risk_r <= 0 or (risk_r / entry) > 0.02: continue

                        pos_size = int((capital * 0.01) / risk_r)
                        if pos_size <= 0: continue

                        entered = True
                        rem = day_df.loc[dt:]
                        outcome = 'EXPIRED'
                        exit_price = rem.iloc[-1]['Close']
                        trail_sl = sl

                        for r_dt, r_row in rem.iloc[1:].iterrows():
                            r_h, r_l = r_row['High'], r_row['Low']
                            if direction == 'LONG':
                                if r_h >= (entry + 0.8 * risk_r):
                                    trail_sl = max(trail_sl, entry) # Breakeven trail
                                if r_h >= target1:
                                    outcome = 'HIT_TARGET'
                                    exit_price = target1
                                    break
                                elif r_l <= trail_sl:
                                    outcome = 'HIT_SL' if trail_sl < entry else 'HIT_BE'
                                    exit_price = trail_sl
                                    break
                            else: # SHORT
                                if r_l <= (entry - 0.8 * risk_r):
                                    trail_sl = min(trail_sl, entry)
                                if r_l <= target1:
                                    outcome = 'HIT_TARGET'
                                    exit_price = target1
                                    break
                                elif r_h >= trail_sl:
                                    outcome = 'HIT_SL' if trail_sl > entry else 'HIT_BE'
                                    exit_price = trail_sl
                                    break

                        mult = 1 if direction == 'LONG' else -1
                        pnl = (exit_price - entry) * pos_size * mult
                        r_m = pnl / (risk_r * pos_size)
                        trades.append({'date': str(t_date), 'symbol': symbol, 'outcome': outcome, 'pnl': pnl, 'r_m': r_m})

        except Exception:
            continue

    df_res = pd.DataFrame(trades)
    if df_res.empty:
        print("No CPR trades triggered")
        return

    total = len(df_res)
    wins = len(df_res[df_res['outcome'] == 'HIT_TARGET'])
    be = len(df_res[df_res['outcome'] == 'HIT_BE'])
    losses = len(df_res[df_res['outcome'] == 'HIT_SL'])
    exp = len(df_res[df_res['outcome'] == 'EXPIRED'])
    net_pnl = df_res['pnl'].sum()

    print("\n" + "="*55)
    print("   CPR NARROW RANGE + VWAP STRATEGY (30-DAY RESULTS)   ")
    print("="*55)
    print(f"Total Trades Taken:    {total} (Selective: ~{total/20:.1f} per day)")
    print(f"Wins / BE / Losses / Exp: {wins} W / {be} BE / {losses} L / {exp} E")
    print(f"WIN RATE ON DECISIVE TRADES: {(wins/(wins+losses)*100 if (wins+losses)>0 else 0):.1f}%")
    print(f"Average R-Multiple:    {df_res['r_m'].mean():+.2f}R")
    print(f"NET PROFIT / LOSS:     Rs. {net_pnl:+,.2f} ({net_pnl/capital*100:+.2f}%)")
    print("="*55)

if __name__ == '__main__':
    run_cpr_backtest()
