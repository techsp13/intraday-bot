"""
VWAP + 20 EMA Trend Pullback Strategy Backtest (30 Days)
Logic:
- Trend condition: Daily ADX > 25 AND 5m 20 EMA > 50 EMA
- Entry: Price pulls back near VWAP (within 0.3%) & bounces
- Exit: Target 1.5R, SL below swing low / EMA 50
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist
from screener import calculate_adx, calculate_vwap, calculate_atr

def run_pullback_backtest():
    symbols = load_watchlist()[:100]
    intraday_batch = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")
    daily_batch = yf.download(symbols, period="60d", interval="1d", progress=False, group_by="ticker")

    trades = []
    capital = 100000.0

    for symbol in symbols:
        try:
            if isinstance(intraday_batch.columns, pd.MultiIndex):
                if symbol not in intraday_batch.columns.levels[0]: continue
                df_5m = intraday_batch[symbol].dropna(subset=['Open', 'High', 'Low', 'Close'])
            else:
                df_5m = intraday_batch.dropna(subset=['Open', 'High', 'Low', 'Close'])

            if isinstance(daily_batch.columns, pd.MultiIndex):
                if symbol not in daily_batch.columns.levels[0]: continue
                df_daily = daily_batch[symbol].dropna(subset=['Open', 'High', 'Low', 'Close'])
            else:
                df_daily = daily_batch.dropna(subset=['Open', 'High', 'Low', 'Close'])

            if df_5m.empty or df_daily.empty or len(df_daily) < 20: continue

            adx_df = calculate_adx(df_daily['High'], df_daily['Low'], df_daily['Close'], period=14)
            dates = sorted(list(set(df_5m.index.date)))

            for trade_date in dates:
                day_df = df_5m[df_5m.index.date == trade_date].copy()
                if len(day_df) < 15: continue

                prior_daily = df_daily[df_daily.index.date < trade_date]
                if prior_daily.empty: continue
                latest_adx = adx_df.loc[prior_daily.index[-1], 'adx']
                if pd.isna(latest_adx) or latest_adx < 22.0: continue  # Strong trend filter

                # Calculate VWAP & EMAs
                day_df['VWAP'] = calculate_vwap(day_df)
                day_df['EMA20'] = day_df['Close'].ewm(span=20, adjust=False).mean()
                day_df['EMA50'] = day_df['Close'].ewm(span=50, adjust=False).mean()

                # Scan session (09:45 to 14:30)
                session = day_df.between_time('09:45', '14:30')
                entered = False

                for dt, row in session.iterrows():
                    if entered: break
                    close = row['Close']
                    low = row['Low']
                    high = row['High']
                    vwap = row['VWAP']
                    ema20 = row['EMA20']
                    ema50 = row['EMA50']

                    # LONG Pullback: 20 EMA > 50 EMA, low touches/nears VWAP or EMA20, close bounces above
                    if ema20 > ema50 and abs(low - vwap)/vwap <= 0.003 and close > vwap:
                        entered = True
                        entry = close
                        sl = min(low, ema50)
                        risk_r = entry - sl
                        if risk_r <= 0 or (risk_r / entry) > 0.02: continue  # max 2% SL cap

                        target1 = entry + 1.5 * risk_r
                        target2 = entry + 2.5 * risk_r

                        # Position Sizing (1% risk)
                        pos_size = int((capital * 0.01) / risk_r)
                        if pos_size <= 0 or (pos_size * entry) > (capital * 0.25): continue

                        # Simulate outcome
                        rem = day_df.loc[dt:]
                        outcome = 'EXPIRED'
                        exit_price = rem.iloc[-1]['Close']

                        for r_dt, r_row in rem.iloc[1:].iterrows():
                            if r_row['High'] >= target1:
                                outcome = 'HIT_T1'
                                exit_price = target1
                                if r_row['High'] >= target2:
                                    outcome = 'HIT_T2'
                                    exit_price = target2
                                break
                            elif r_row['Low'] <= sl:
                                outcome = 'HIT_SL'
                                exit_price = sl
                                break

                        pnl = (exit_price - entry) * pos_size
                        r_mult = pnl / (risk_r * pos_size)
                        trades.append({
                            'date': str(trade_date),
                            'symbol': symbol,
                            'outcome': outcome,
                            'pnl': pnl,
                            'r_multiple': r_mult
                        })

        except Exception:
            continue

    df_t = pd.DataFrame(trades)
    if df_t.empty:
        print("No trades found")
        return

    wins = len(df_t[df_t['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    losses = len(df_t[df_t['outcome'] == 'HIT_SL'])
    exp = len(df_t[df_t['outcome'] == 'EXPIRED'])
    total = len(df_t)
    net_pnl = df_t['pnl'].sum()

    print("\n" + "="*50)
    print("   VWAP + EMA PULLBACK STRATEGY (30-DAY BACKTEST)   ")
    print("="*50)
    print(f"Total Trades:       {total}")
    print(f"Wins / Losses / Exp:{wins} W / {losses} L / {exp} E")
    print(f"Win Rate (on hits): {(wins/(wins+losses)*100 if (wins+losses)>0 else 0):.1f}%")
    print(f"Average R-Multiple: {df_t['r_multiple'].mean():+.2f}R")
    print(f"NET PROFIT / LOSS:  Rs. {net_pnl:+,.2f} ({net_pnl/capital*100:+.2f}%)")
    print("="*50)

if __name__ == '__main__':
    run_pullback_backtest()
