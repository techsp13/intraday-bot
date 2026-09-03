import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

def run_10_day_5x_report():
    conn = sqlite3.connect('data/picks.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM picks ORDER BY date ASC, id ASC")
    rows = c.fetchall()
    conn.close()

    df_all = pd.DataFrame([dict(r) for r in rows])
    unique_dates = sorted(df_all['date'].unique())[-10:]

    initial_capital = 100000.0 # Rs. 1 Lakh in Zerodha Demat
    position_value_per_stock = 100000.0 # Rs. 1 Lakh exposure per stock (Rs. 20,000 cash margin * 5x leverage)

    print("=" * 95)
    print("📊 10-DAY DAY-BY-DAY PERFORMANCE WITH ₹1,00,000 ZERODHA CAPITAL (5x MIS LEVERAGE)")
    print("=" * 95)

    daily_results = []
    total_cum_pnl = 0.0

    for d in unique_dates:
        day_picks = df_all[df_all['date'] == d]
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
        top_gainers = []

        for p in day_trades:
            sym = p.get('symbol')
            ticker = p.get('ticker', f"{sym}.NS")
            direction = p.get('direction', 'LONG').upper()
            entry = float(p.get('entry', 0.0))
            if entry <= 0: continue

            # Quantity sized for Rs. 1 Lakh Position Value
            qty = max(1, int(position_value_per_stock / entry))

            sl = round(entry * 0.98 if direction == 'LONG' else entry * 1.02, 2)
            t1 = round(entry * 1.03 if direction == 'LONG' else entry * 0.97, 2)
            t2 = round(entry * 1.05 if direction == 'LONG' else entry * 0.95, 2)

            try:
                hist = yf.download(ticker, period="45d", interval="1d", progress=False)
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
                
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

            day_pnl += pnl
            if pnl > 0:
                day_wins += 1
                top_gainers.append(f"{sym} (+Rs.{pnl:,.0f})")
            elif pnl < 0:
                day_losses += 1

        total_cum_pnl += day_pnl
        daily_results.append({
            'date': d,
            'trades': len(day_trades),
            'wins': day_wins,
            'losses': day_losses,
            'day_pnl': day_pnl,
            'cum_pnl': total_cum_pnl,
            'gainers': ", ".join(top_gainers) if top_gainers else "Losses Capped by 2% SL"
        })

    print(f"{'Date':<12} | {'Trades':<7} | {'Win/Loss':<8} | {'Daily P&L (₹)':<16} | {'Account Balance (₹)':<20} | Top Winning Movers")
    print("-" * 95)

    current_account = initial_capital
    for r in daily_results:
        current_account = initial_capital + r['cum_pnl']
        pnl_sign = "+" if r['day_pnl'] >= 0 else ""
        print(f"{r['date']:<12} | {r['trades']:<7} | {r['wins']}W / {r['losses']}L   | {pnl_sign}₹{r['day_pnl']:>10.2f}   | ₹{current_account:>13,.2f}      | {r['gainers']}")

    print("=" * 95)
    total_pct = (total_cum_pnl / initial_capital) * 100.0
    tot_sign = "+" if total_cum_pnl >= 0 else ""

    print(f"\n🏆 10-DAY TOTAL PERFORMANCE SUMMARY (₹1 LAKH CAPITAL):")
    print(f"▸ Initial Demat Balance:       ₹{initial_capital:,.2f}")
    print(f"▸ Total 10-Day Realized Profit: {tot_sign}₹{total_cum_pnl:,.2f}")
    print(f"▸ Ending Demat Balance:        ₹{(initial_capital + total_cum_pnl):,.2f}")
    print(f"▸ NET ROI IN 10 TRADING DAYS:  {tot_sign}{total_pct:.2f}% GAIN")
    print("=" * 95)

if __name__ == '__main__':
    run_10_day_5x_report()
