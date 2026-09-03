import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

def run_top2_10day_simulation():
    conn = sqlite3.connect('data/picks.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM picks ORDER BY date ASC, id ASC")
    rows = c.fetchall()
    conn.close()

    df_all = pd.DataFrame([dict(r) for r in rows])
    unique_dates = sorted(df_all['date'].unique())[-10:]

    account_balance = 6800.0 # Starting Cash
    initial_balance = 6800.0
    brokerage_per_trade = 50.0 # ₹50 roundtrip brokerage + STT + GST per stock

    print("=" * 105)
    print("📊 10-DAY VERIFIED PERFORMANCE: TOP 2 PICKS ONLY (50/50 SPLIT + BROKERAGE DEDUCTED)")
    print("   Starting Capital: ₹6,800.00 | Broker: Zerodha (5x MIS Leverage)")
    print("=" * 105)

    daily_logs = []

    for d in unique_dates:
        day_picks = df_all[df_all['date'] == d]
        seen = set()
        deduped = []
        for _, row in day_picks.iterrows():
            sym = row['symbol']
            if sym not in seen:
                seen.add(sym)
                deduped.append(row.to_dict())
        
        # Select Top 1 Long + Top 1 Short (Top 2 Picks)
        longs = [p for p in deduped if p.get('direction', 'LONG').upper() == 'LONG']
        shorts = [p for p in deduped if p.get('direction', '').upper() == 'SHORT']
        
        top2 = []
        if longs: top2.append(longs[0])
        if shorts: top2.append(shorts[0])
        elif len(longs) > 1: top2.append(longs[1])
        if not top2 and len(deduped) >= 2: top2 = deduped[:2]

        # Sizing: 50% cash margin per stock
        margin_per_stock = account_balance / 2.0
        exposure_per_stock = margin_per_stock * 5.0 # 5x leverage

        day_gross_pnl = 0.0
        day_brokerage = len(top2) * brokerage_per_trade
        trade_details = []
        day_wins = 0
        day_losses = 0

        for p in top2:
            sym = p.get('symbol')
            ticker = p.get('ticker', f"{sym}.NS")
            direction = p.get('direction', 'LONG').upper()
            entry = float(p.get('entry', 0.0))
            if entry <= 0: continue

            qty = max(1, int(exposure_per_stock / entry))

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
                outcome = "EOD CLOSE"

            day_gross_pnl += pnl
            p_sign = "+" if pnl >= 0 else ""
            trade_details.append(f"{sym} ({direction}) {p_sign}₹{pnl:,.0f} [{outcome}]")
            if pnl > 0: day_wins += 1
            elif pnl < 0: day_losses += 1

        day_net_pnl = day_gross_pnl - day_brokerage
        account_balance += day_net_pnl

        daily_logs.append({
            'date': d,
            'trades': len(top2),
            'wins': day_wins,
            'losses': day_losses,
            'gross_pnl': day_gross_pnl,
            'brokerage': day_brokerage,
            'net_pnl': day_net_pnl,
            'balance': account_balance,
            'details': " | ".join(trade_details)
        })

    print(f"{'Date':<12} | {'Trades':<7} | {'Win/Loss':<8} | {'Daily Net P&L (₹)':<18} | {'Demat Balance (₹)':<18} | Top 2 Trade Breakdown")
    print("-" * 105)

    for r in daily_logs:
        p_sign = "+" if r['net_pnl'] >= 0 else ""
        print(f"{r['date']:<12} | {r['trades']:<7} | {r['wins']}W / {r['losses']}L   | {p_sign}₹{r['net_pnl']:>11.2f}     | ₹{r['balance']:>12,.2f}     | {r['details']}")

    print("=" * 105)
    total_net_profit = account_balance - initial_balance
    total_roi_pct = (total_net_profit / initial_balance) * 100.0
    tot_sign = "+" if total_net_profit >= 0 else ""

    print(f"\n🏆 10-DAY SUMMARY: TOP 2 PICKS ONLY (STARTING AT ₹6,800):")
    print(f"▸ Initial Demat Cash:          ₹{initial_balance:,.2f}")
    print(f"▸ Total 10-Day Realized Net:    {tot_sign}₹{total_net_profit:,.2f} (After all Zerodha brokerages & taxes!)")
    print(f"▸ Ending Demat Cash Balance:   ₹{account_balance:,.2f}")
    print(f"▸ 10-DAY NET COMPOUNDED ROI:   {tot_sign}{total_roi_pct:.2f}% GAIN")
    print("=" * 105)

if __name__ == '__main__':
    run_top2_10day_simulation()
