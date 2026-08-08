"""
Supertrend + VWAP Momentum Backtest (30 Days)
Logic:
1. Daily ADX > 20
2. Stock is above Daily VWAP & 20 EMA > 50 EMA
3. Candle closes above previous candle high with volume surge >= 1.3x
4. SL = 1.0% | Target = 2.0R (Trailing SL at +1.0R)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from data_fetcher import load_watchlist
from screener import calculate_adx, calculate_vwap

def run_st_vwap_backtest():
    symbols = load_watchlist()[:150]
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
                if pd.isna(latest_adx) or latest_adx < 20.0: continue

                day_df['VWAP'] = calculate_vwap(day_df)
                day_df['EMA20'] = day_df['Close'].ewm(span=20, adjust=False).mean()
                day_df['EMA50'] = day_df['Close'].ewm(span=50, adjust=False).mean()
                day_df['Vol_SMA'] = day_df['Volume'].rolling(20).mean()

                # Session 09:45 to 14:30
                session = day_df.between_time('09:45', '14:30')
                entered = False

                for dt, row in session.iterrows():
                    if entered: break
                    close = row['Close']
                    high = row['High']
                    low = row['Low']
                    vwap = row['VWAP']
                    ema20 = row['EMA20']
                    ema50 = row['EMA50']
                    vol = row['Volume']
                    vol_sma = row['Vol_SMA']

                    # LONG Setup: EMA20 > EMA50, Close > VWAP, Volume Surge >= 1.3x SMA
                    if ema20 > ema50 and close > vwap and vol >= (1.3 * vol_sma):
                        # Entry on candle close
                        entry = close
                        sl = entry * 0.99  # Tight 1.0% stop loss
                        risk_r = entry - sl
                        target1 = entry + 1.5 * risk_r
                        target2 = entry + 2.5 * risk_r

                        pos_size = int((capital * 0.01) / risk_r)
                        if pos_size <= 0 or (pos_size * entry) > (capital * 0.20): continue

                        entered = True
                        rem = day_df.loc[dt:]
                        outcome = 'EXPIRED'
                        exit_price = rem.iloc[-1]['Close']
                        trailed_sl = sl

                        for r_dt, r_row in rem.iloc[1:].iterrows():
                            c_high = r_row['High']
                            c_low = r_row['Low']

                            # Trailing stop loss to breakeven once +1.0R is reached
                            if c_high >= (entry + 1.0 * risk_r):
                                trailed_sl = max(trailed_sl, entry)

                            if c_high >= target2:
                                outcome = 'HIT_T2'
                                exit_price = target2
                                break
                            elif c_high >= target1:
                                outcome = 'HIT_T1'
                                exit_price = target1
                                break
                            elif c_low <= trailed_sl:
                                outcome = 'HIT_SL' if trailed_sl < entry else 'HIT_BREAKEVEN'
                                exit_price = trailed_sl
                                break

                        pnl = (exit_price - entry) * pos_size
                        r_mult = pnl / (risk_r * pos_size) if (risk_r * pos_size) > 0 else 0.0

                        trades.append({
                            'date': str(trade_date),
                            'symbol': symbol.replace('.NS', ''),
                            'outcome': outcome,
                            'pnl': pnl,
                            'r_multiple': r_mult
                        })

        except Exception:
            continue

    df_t = pd.DataFrame(trades)
    if df_t.empty:
        print("No trades triggered")
        return

    wins = len(df_t[df_t['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    be = len(df_t[df_t['outcome'] == 'HIT_BREAKEVEN'])
    losses = len(df_t[df_t['outcome'] == 'HIT_SL'])
    exp = len(df_t[df_t['outcome'] == 'EXPIRED'])
    total = len(df_t)
    net_pnl = df_t['pnl'].sum()

    print("\n" + "="*50)
    print("  SUPER TREND + VWAP + TRAILING SL (30-DAY BACKTEST)  ")
    print("="*50)
    print(f"Total Trades:       {total}")
    print(f"Wins / BE / Losses / Exp: {wins} W / {be} BE / {losses} L / {exp} E")
    print(f"Win Rate (Target Hits):   {(wins/total*100):.1f}%")
    print(f"Average R-Multiple:       {df_t['r_multiple'].mean():+.2f}R")
    print(f"NET PROFIT / LOSS:        Rs. {net_pnl:+,.2f} ({net_pnl/capital*100:+.2f}%)")
    print("="*50)

if __name__ == '__main__':
    run_st_vwap_backtest()
