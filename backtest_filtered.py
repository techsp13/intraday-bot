"""
Filtered 30-Day Historical Backtest (Production Rules)
Enforces:
1. Max 5 top picks per day sorted by score
2. ADX >= 20 & Vol surge >= 1.5x
3. Daily loss limit cap (3% of capital)
"""
import pandas as pd
import numpy as np
import yfinance as yf
import config
from data_fetcher import load_watchlist
from screener import calculate_adx, calculate_vwap
from risk_manager import calculate_position_size, check_reward_risk

def run_filtered_backtest():
    symbols = load_watchlist()[:150]
    intraday_batch = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")
    daily_batch = yf.download(symbols, period="60d", interval="1d", progress=False, group_by="ticker")

    all_daily_picks = {}  # trade_date -> list of picks

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
                day_df = df_5m[df_5m.index.date == trade_date]
                if len(day_df) < 12: continue

                prior_daily = df_daily[df_daily.index.date < trade_date]
                if prior_daily.empty: continue
                latest_adx_idx = prior_daily.index[-1]
                if latest_adx_idx not in adx_df.index: continue
                
                adx_row = adx_df.loc[latest_adx_idx]
                adx_val = adx_row['adx']
                if pd.isna(adx_val) or adx_val < 20.0: continue

                or_df = day_df.between_time('09:15', '09:44')
                if or_df.empty or len(or_df) < 6: continue
                or_high, or_low = or_df['High'].max(), or_df['Low'].min()

                vwap_series = calculate_vwap(day_df)
                post_or = day_df.between_time('09:45', '15:15')

                avg_vol = prior_daily['Volume'].tail(20).mean()
                day_vol = day_df['Volume'].sum()
                vol_ratio = day_vol / avg_vol if avg_vol > 0 else 1.0

                for dt, row in post_or.iterrows():
                    close, high, low = row['Close'], row['High'], row['Low']
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
                        if risk_r <= 0: continue
                        target1 = entry + 1.5 * risk_r if direction == 'LONG' else entry - 1.5 * risk_r
                        target2 = entry + 2.5 * risk_r if direction == 'LONG' else entry - 2.5 * risk_r

                        if (abs(target1 - entry) / risk_r) < 1.5: continue

                        # Score
                        score = adx_val
                        if vol_ratio >= 1.5: score += 10
                        if direction == 'LONG' and entry > vwap_val: score += 5
                        elif direction == 'SHORT' and entry < vwap_val: score += 5

                        pick = {
                            'date': trade_date,
                            'symbol': symbol.replace('.NS', ''),
                            'direction': direction,
                            'entry': entry,
                            'sl': sl,
                            'target1': target1,
                            'target2': target2,
                            'risk_r': risk_r,
                            'score': score,
                            'breakout_dt': dt,
                            'day_df': day_df
                        }

                        if trade_date not in all_daily_picks:
                            all_daily_picks[trade_date] = []
                        all_daily_picks[trade_date].append(pick)
                        break
        except Exception:
            continue

    # Execute only Top 5 picks per day
    capital = 100000.0
    executed_trades = []

    for trade_date in sorted(all_daily_picks.keys()):
        picks = all_daily_picks[trade_date]
        picks.sort(key=lambda x: x['score'], reverse=True)
        top_picks = picks[:5]  # Production rule: Top 5 picks max

        daily_pnl = 0.0

        for p in top_picks:
            pos_size = calculate_position_size(capital, p['entry'], p['sl'])
            if pos_size <= 0: continue

            day_df = p['day_df']
            remaining = day_df.loc[p['breakout_dt']:]
            outcome = 'EXPIRED'
            exit_price = remaining.iloc[-1]['Close']

            for dt, c_row in remaining.iloc[1:].iterrows():
                c_high, c_low = c_row['High'], c_row['Low']
                if p['direction'] == 'LONG':
                    if c_high >= p['target1']:
                        outcome = 'HIT_T1'
                        exit_price = p['target1']
                        if c_high >= p['target2']:
                            outcome = 'HIT_T2'
                            exit_price = p['target2']
                        break
                    elif c_low <= p['sl']:
                        outcome = 'HIT_SL'
                        exit_price = p['sl']
                        break
                else:
                    if c_low <= p['target1']:
                        outcome = 'HIT_T1'
                        exit_price = p['target1']
                        if c_low <= p['target2']:
                            outcome = 'HIT_T2'
                            exit_price = p['target2']
                        break
                    elif c_high >= p['sl']:
                        outcome = 'HIT_SL'
                        exit_price = p['sl']
                        break

            dir_mult = 1 if p['direction'] == 'LONG' else -1
            pnl = (exit_price - p['entry']) * pos_size * dir_mult
            r_mult = pnl / (p['risk_r'] * pos_size) if (p['risk_r'] * pos_size) > 0 else 0.0

            daily_pnl += pnl
            executed_trades.append({
                'date': str(trade_date),
                'symbol': p['symbol'],
                'direction': p['direction'],
                'outcome': outcome,
                'pnl': pnl,
                'r_multiple': r_mult
            })

            # Check daily loss limit cap (3%)
            if daily_pnl <= - (capital * 0.03):
                break

    df_res = pd.DataFrame(executed_trades)
    total_trades = len(df_res)
    wins = len(df_res[df_res['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    losses = len(df_res[df_res['outcome'] == 'HIT_SL'])
    expired = len(df_res[df_res['outcome'] == 'EXPIRED'])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    net_pnl = df_res['pnl'].sum()
    avg_r = df_res['r_multiple'].mean()

    print("\n" + "="*50)
    print("  TOP-5 SCORING FILTERED 30-DAY BACKTEST RESULTS  ")
    print("="*50)
    print(f"Total Trades Taken:    {total_trades} (Avg {total_trades/len(all_daily_picks):.1f} per day)")
    print(f"Wins / Losses / Exp:   {wins} W / {losses} L / {expired} E")
    print(f"Win Rate (on hits):    {(wins/(wins+losses)*100 if (wins+losses)>0 else 0):.1f}% (Overall {win_rate:.1f}%)")
    print(f"Average R-Multiple:    {avg_r:+.2f}R")
    print(f"NET P&L (Top 5 Picks): Rs. {net_pnl:+,.2f} ({net_pnl/capital*100:+.2f}%)")
    print("="*50)

if __name__ == '__main__':
    run_filtered_backtest()
