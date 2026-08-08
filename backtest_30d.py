"""
30-Day Historical Backtest for Intraday ORB Strategy
Evaluates performance on 5-min intraday candles over the past month.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import config
from data_fetcher import load_watchlist, compute_avg_daily_volume, compute_avg_daily_turnover
from screener import calculate_adx, calculate_vwap, extract_opening_range, detect_breakouts
from risk_manager import calculate_position_size, check_reward_risk

def run_30d_backtest():
    print("=== Running 30-Day Historical Backtest ===")
    symbols = load_watchlist()[:100]  # Top 100 most liquid NIFTY stocks for fast backtest
    print(f"Backtesting strategy across {len(symbols)} symbols over last 30 days...")

    # Fetch 30 days of 5m candles and 60 days of daily data
    print("Downloading historical data...")
    intraday_batch = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")
    daily_batch = yf.download(symbols, period="60d", interval="1d", progress=False, group_by="ticker")

    all_trades = []
    capital = config.CAPITAL_BASE

    for symbol in symbols:
        try:
            # Extract symbol DataFrames
            if isinstance(intraday_batch.columns, pd.MultiIndex):
                if symbol not in intraday_batch.columns.levels[0]:
                    continue
                df_5m = intraday_batch[symbol].dropna(subset=['Open', 'High', 'Low', 'Close'])
            else:
                df_5m = intraday_batch.dropna(subset=['Open', 'High', 'Low', 'Close'])

            if isinstance(daily_batch.columns, pd.MultiIndex):
                if symbol not in daily_batch.columns.levels[0]:
                    continue
                df_daily = daily_batch[symbol].dropna(subset=['Open', 'High', 'Low', 'Close'])
            else:
                df_daily = daily_batch.dropna(subset=['Open', 'High', 'Low', 'Close'])

            if df_5m.empty or df_daily.empty or len(df_daily) < 20:
                continue

            # Compute daily ADX
            adx_df = calculate_adx(df_daily['High'], df_daily['Low'], df_daily['Close'], period=config.ADX_PERIOD)

            # Group 5m data by trading day
            dates = sorted(list(set(df_5m.index.date)))

            for trade_date in dates:
                day_df = df_5m[df_5m.index.date == trade_date]
                if len(day_df) < 12:  # Needs at least morning session
                    continue

                # Get prior daily ADX
                prior_daily = df_daily[df_daily.index.date < trade_date]
                if prior_daily.empty:
                    continue
                latest_adx_idx = prior_daily.index[-1]
                if latest_adx_idx not in adx_df.index:
                    continue
                adx_val = adx_df.loc[latest_adx_idx, 'adx']

                if pd.isna(adx_val) or adx_val < config.ADX_THRESHOLD:
                    continue  # Filter: Trend strength

                # Opening Range (09:15 to 09:44)
                or_df = day_df.between_time('09:15', '09:44')
                if or_df.empty or len(or_df) < 6:
                    continue
                or_high = or_df['High'].max()
                or_low = or_df['Low'].min()

                # VWAP
                vwap_series = calculate_vwap(day_df)

                # Detect Breakout
                post_or = day_df.between_time('09:45', '15:15')
                found = False

                for dt, row in post_or.iterrows():
                    if found:
                        break
                    close = row['Close']
                    high = row['High']
                    low = row['Low']
                    vwap_val = vwap_series.loc[dt]

                    direction = None
                    if close > or_high and close > vwap_val:
                        direction = 'LONG'
                        entry = close
                        sl = min(or_low, low)
                    elif close < or_low and close < vwap_val:
                        direction = 'SHORT'
                        entry = close
                        sl = max(or_high, high)

                    if direction:
                        risk_r = abs(entry - sl)
                        if risk_r <= 0:
                            continue
                        target1 = entry + 1.5 * risk_r if direction == 'LONG' else entry - 1.5 * risk_r
                        target2 = entry + 2.5 * risk_r if direction == 'LONG' else entry - 2.5 * risk_r

                        if not check_reward_risk(entry, sl, target1):
                            continue

                        pos_size = calculate_position_size(capital, entry, sl)
                        if pos_size <= 0:
                            continue

                        # Simulate Trade Outcome on remaining candles of the day
                        remaining_candles = day_df.loc[dt:]
                        outcome = 'EXPIRED'
                        exit_price = remaining_candles.iloc[-1]['Close']

                        for c_dt, c_row in remaining_candles.iloc[1:].iterrows():
                            c_high = c_row['High']
                            c_low = c_row['Low']

                            if direction == 'LONG':
                                if c_high >= target1:
                                    outcome = 'HIT_T1'
                                    exit_price = target1
                                    if c_high >= target2:
                                        outcome = 'HIT_T2'
                                        exit_price = target2
                                    break
                                elif c_low <= sl:
                                    outcome = 'HIT_SL'
                                    exit_price = sl
                                    break
                            else:  # SHORT
                                if c_low <= target1:
                                    outcome = 'HIT_T1'
                                    exit_price = target1
                                    if c_low <= target2:
                                        outcome = 'HIT_T2'
                                        exit_price = target2
                                    break
                                elif c_high >= sl:
                                    outcome = 'HIT_SL'
                                    exit_price = sl
                                    break

                        dir_mult = 1 if direction == 'LONG' else -1
                        pnl = (exit_price - entry) * pos_size * dir_mult
                        r_multiple = pnl / (risk_r * pos_size) if (risk_r * pos_size) > 0 else 0.0

                        all_trades.append({
                            'date': str(trade_date),
                            'symbol': symbol.replace('.NS', ''),
                            'direction': direction,
                            'entry': entry,
                            'sl': sl,
                            'target1': target1,
                            'outcome': outcome,
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'r_multiple': r_multiple
                        })
                        found = True

        except Exception as e:
            continue

    # Compile Backtest Summary
    if not all_trades:
        print("No trades triggered in the backtest period.")
        return

    df_trades = pd.DataFrame(all_trades)
    total_trades = len(df_trades)
    wins = len(df_trades[df_trades['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    losses = len(df_trades[df_trades['outcome'] == 'HIT_SL'])
    expired = len(df_trades[df_trades['outcome'] == 'EXPIRED'])
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

    total_pnl = df_trades['pnl'].sum()
    avg_r = df_trades['r_multiple'].mean()
    profit_factor = abs(df_trades[df_trades['pnl'] > 0]['pnl'].sum() / df_trades[df_trades['pnl'] < 0]['pnl'].sum()) if abs(df_trades[df_trades['pnl'] < 0]['pnl'].sum()) > 0 else np.nan

    print("\n" + "="*50)
    print("      30-DAY BACKTEST PERFORMANCE RESULTS      ")
    print("="*50)
    print(f"Period:                Last 30 Days")
    print(f"Stock Universe:        Top 100 Liquid NSE Stocks")
    print(f"Capital Base:          Rs. {capital:,.2f}")
    print(f"Risk Per Trade:        1.0% (Rs. 1,000)")
    print("-" * 50)
    print(f"Total Trades Taken:    {total_trades}")
    print(f"Wins / Losses / Exp:   {wins} W / {losses} L / {expired} E")
    print(f"Win Rate:              {win_rate:.1f}%")
    print(f"Profit Factor:         {profit_factor:.2f}")
    print(f"Average R-Multiple:    {avg_r:+.2f}R")
    print("-" * 50)
    print(f"NET PROFIT / LOSS:     Rs. {total_pnl:+,.2f} ({total_pnl/capital*100:+.2f}%)")
    print(f"Ending Capital:        Rs. {capital + total_pnl:,.2f}")
    print("="*50)

if __name__ == '__main__':
    run_30d_backtest()
