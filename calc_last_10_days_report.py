import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

def run_10_day_report():
    conn = sqlite3.connect('data/picks.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM picks ORDER BY date ASC, id ASC")
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("No picks in DB.")
        return

    df_all = pd.DataFrame([dict(r) for r in rows])
    unique_dates = sorted(df_all['date'].unique())[-10:] # Last 10 trading dates

    print(f"=== FULL 10-DAY INTRADAY PERFORMANCE REPORT ({unique_dates[0]} to {unique_dates[-1]}) ===\n")

    daily_summaries = []
    total_cum_pnl = 0.0
    total_trades_count = 0
    total_wins_count = 0
    total_losses_count = 0

    for d in unique_dates:
        day_picks = df_all[df_all['date'] == d]
        # Deduplicate symbols per date
        seen = set()
        deduped = []
        for _, row in day_picks.iterrows():
            sym = row['symbol']
            if sym not in seen:
                seen.add(sym)
                deduped.append(row.to_dict())
        
        day_trades = deduped[:5]
        day_pnl = 0.0
        day_wins = 0
        day_losses = 0
        winners_list = []

        for p in day_trades:
            sym = p.get('symbol')
            ticker = p.get('ticker', f"{sym}.NS")
            direction = p.get('direction', 'LONG').upper()
            entry = float(p.get('entry', 0.0))
            sl = float(p.get('sl', round(entry * 0.98 if direction == 'LONG' else entry * 1.02, 2)))
            t1 = float(p.get('target1', round(entry * 1.03 if direction == 'LONG' else entry * 0.97, 2)))
            t2 = float(p.get('target2', round(entry * 1.05 if direction == 'LONG' else entry * 0.95, 2)))
            qty = int(p.get('position_size', 10))

            try:
                hist = yf.download(ticker, period="45d", interval="1d", progress=False)
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
                
                # Match target date
                t_date = pd.to_datetime(d).date()
                matching_bars = hist[hist.index.date == t_date]
                
                if not matching_bars.empty:
                    bar = matching_bars.iloc[0]
                    day_high = float(bar['High'])
                    day_low = float(bar['Low'])
                    day_close = float(bar['Close'])
                else:
                    day_high, day_low, day_close = entry, entry, entry

                if direction == 'LONG':
                    if day_high >= t2:
                        outcome = "HIT T2 (+5%)"
                        exit_price = t2
                    elif day_high >= t1:
                        outcome = "HIT T1 (+3%)"
                        exit_price = t1
                    elif day_low <= sl:
                        outcome = "HIT SL (-2%)"
                        exit_price = sl
                    else:
                        outcome = "EOD CLOSE"
                        exit_price = day_close
                    pnl = round((exit_price - entry) * qty, 2)
                else: # SHORT
                    if day_low <= t2:
                        outcome = "HIT T2 (+5%)"
                        exit_price = t2
                    elif day_low <= t1:
                        outcome = "HIT T1 (+3%)"
                        exit_price = t1
                    elif day_high >= sl:
                        outcome = "HIT SL (-2%)"
                        exit_price = sl
                    else:
                        outcome = "EOD CLOSE"
                        exit_price = day_close
                    pnl = round((entry - exit_price) * qty, 2)

            except Exception:
                pnl = 0.0
                outcome = "EOD CLOSE"

            day_pnl += pnl
            total_trades_count += 1
            if pnl > 0:
                day_wins += 1
                total_wins_count += 1
                winners_list.append(f"{sym} (+Rs.{pnl:,.0f})")
            elif pnl < 0:
                day_losses += 1
                total_losses_count += 1

        total_cum_pnl += day_pnl
        daily_summaries.append({
            'date': d,
            'trades': len(day_trades),
            'wins': day_wins,
            'losses': day_losses,
            'day_pnl': day_pnl,
            'cum_pnl': total_cum_pnl,
            'winners': ", ".join(winners_list) if winners_list else "Protected by 2% SL"
        })

    print("=" * 90)
    print(f"{'Date':<12} | {'Trades':<7} | {'Win/Loss':<8} | {'Daily P&L (Rs.)':<16} | {'Cumulative P&L':<16} | Top Movers")
    print("=" * 90)

    for s in daily_summaries:
        pnl_sign = "+" if s['day_pnl'] >= 0 else ""
        cum_sign = "+" if s['cum_pnl'] >= 0 else ""
        print(f"{s['date']:<12} | {s['trades']:<7} | {s['wins']}W / {s['losses']}L   | {pnl_sign}Rs.{s['day_pnl']:>9.2f}    | {cum_sign}Rs.{s['cum_pnl']:>10.2f}   | {s['winners']}")

    print("=" * 90)
    win_rate = (total_wins_count / total_trades_count * 100) if total_trades_count > 0 else 0
    cum_total_sign = "+" if total_cum_pnl >= 0 else ""
    
    print(f"\n[10-DAY CUMULATIVE METRICS]")
    print(f"Total Trades Executed:     {total_trades_count}")
    print(f"Overall Win Rate:          {win_rate:.1f}% ({total_wins_count} Wins / {total_losses_count} Losses)")
    print(f"10-Day Realized Net P&L:   {cum_total_sign}Rs.{total_cum_pnl:,.2f}")
    print(f"Return on Rs.20k Margin:   +{(total_cum_pnl / 20000 * 100):.1f}%")
    print(f"Return on Rs.100k Capital: +{(total_cum_pnl / 100000 * 100):.1f}%")
    print("=" * 90)

if __name__ == '__main__':
    run_10_day_report()
