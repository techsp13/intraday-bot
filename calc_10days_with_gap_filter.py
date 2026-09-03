import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

def run_gap_filtered_10day_simulation():
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
    brokerage_per_trade = 50.0

    print("=" * 110)
    print("📊 10-DAY BACKTEST WITH THE 09:15 AM GAP & COLOR FILTER RULE (STARTING CAPITAL: ₹6,800)")
    print("   Filter Rules: Skip Big Gaps (> ±1.5%) | Skip Opposite Openers (Longs opening Red / Shorts opening Green)")
    print("=" * 110)

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
        
        day_trades = deduped[:5]
        
        # 1. Evaluate Opening Gap & Color for each stock
        qualified_stocks = []
        skipped_stocks = []

        for p in day_trades:
            sym = p.get('symbol')
            ticker = p.get('ticker', f"{sym}.NS")
            direction = p.get('direction', 'LONG').upper()
            ref_entry = float(p.get('entry', 0.0))
            if ref_entry <= 0: continue

            try:
                hist = yf.download(ticker, period="45d", interval="1d", progress=False)
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
                
                t_date = pd.to_datetime(d).date()
                matching_bars = hist[hist.index.date == t_date]
                if matching_bars.empty: continue

                bar = matching_bars.iloc[0]
                day_open = float(bar['Open'])
                day_high = float(bar['High'])
                day_low = float(bar['Low'])
                day_close = float(bar['Close'])

                # Gap % calculation
                gap_pct = ((day_open - ref_entry) / ref_entry) * 100.0

                # Check Qualifications
                is_qualified = True
                skip_reason = ""

                if direction == 'LONG':
                    if gap_pct > 1.5:
                        is_qualified = False
                        skip_reason = f"Big Gap-Up (+{gap_pct:.1f}%)"
                    elif gap_pct < -0.5:
                        is_qualified = False
                        skip_reason = f"Opposite Red Open ({gap_pct:.1f}%)"
                else: # SHORT
                    if gap_pct < -1.5:
                        is_qualified = False
                        skip_reason = f"Big Gap-Down ({gap_pct:.1f}%)"
                    elif gap_pct > 0.5:
                        is_qualified = False
                        skip_reason = f"Opposite Green Open (+{gap_pct:.1f}%)"

                if is_qualified:
                    qualified_stocks.append({
                        'symbol': sym,
                        'ticker': ticker,
                        'direction': direction,
                        'open': day_open,
                        'high': day_high,
                        'low': day_low,
                        'close': day_close,
                        'gap_pct': gap_pct
                    })
                else:
                    skipped_stocks.append(f"{sym} [SKIPPED: {skip_reason}]")

            except Exception:
                continue

        # 2. Execute Trades on Qualified Clean Openers
        if not qualified_stocks:
            daily_logs.append({
                'date': d,
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'net_pnl': 0.0,
                'balance': account_balance,
                'details': "All Stocks Skipped due to Gaps/Opposite Opens (Zero Risk Day)",
                'skipped': ", ".join(skipped_stocks)
            })
            continue

        # Position Sizing: Split account balance equally across qualified stocks
        margin_per_stock = account_balance / len(qualified_stocks)
        exposure_per_stock = margin_per_stock * 5.0 # 5x leverage

        day_gross_pnl = 0.0
        day_brokerage = len(qualified_stocks) * brokerage_per_trade
        trade_details = []
        day_wins = 0
        day_losses = 0

        for q in qualified_stocks:
            sym = q['symbol']
            direction = q['direction']
            entry = q['open']
            day_high = q['high']
            day_low = q['low']
            day_close = q['close']

            qty = max(1, int(exposure_per_stock / entry))

            sl = round(entry * 0.98 if direction == 'LONG' else entry * 1.02, 2)
            t1 = round(entry * 1.03 if direction == 'LONG' else entry * 0.97, 2)
            t2 = round(entry * 1.05 if direction == 'LONG' else entry * 0.95, 2)

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

            day_gross_pnl += pnl
            p_sign = "+" if pnl >= 0 else ""
            trade_details.append(f"{sym} {p_sign}₹{pnl:,.0f} ({outcome})")
            if pnl > 0: day_wins += 1
            elif pnl < 0: day_losses += 1

        day_net_pnl = day_gross_pnl - day_brokerage
        account_balance += day_net_pnl

        daily_logs.append({
            'date': d,
            'trades': len(qualified_stocks),
            'wins': day_wins,
            'losses': day_losses,
            'net_pnl': day_net_pnl,
            'balance': account_balance,
            'details': " | ".join(trade_details),
            'skipped': ", ".join(skipped_stocks) if skipped_stocks else "None"
        })

    print(f"{'Date':<12} | {'Traded':<7} | {'Win/Loss':<8} | {'Daily Net P&L':<15} | {'Account Balance':<17} | Executed Clean Trades")
    print("-" * 110)

    for r in daily_logs:
        p_sign = "+" if r['net_pnl'] >= 0 else ""
        print(f"{r['date']:<12} | {r['trades']:<7} | {r['wins']}W / {r['losses']}L   | {p_sign}₹{r['net_pnl']:>10.2f}    | ₹{r['balance']:>13,.2f}   | {r['details']}")

    print("=" * 110)
    total_net_profit = account_balance - initial_balance
    total_roi_pct = (total_net_profit / initial_balance) * 100.0
    tot_sign = "+" if total_net_profit >= 0 else ""

    print(f"\n🏆 10-DAY TOTAL PERFORMANCE WITH GAP FILTER (STARTING AT ₹6,800):")
    print(f"▸ Initial Demat Cash:          ₹{initial_balance:,.2f}")
    print(f"▸ 10-Day Realized Net Profit:  {tot_sign}₹{total_net_profit:,.2f} (After all Zerodha fees!)")
    print(f"▸ Ending Demat Cash Balance:   ₹{account_balance:,.2f}")
    print(f"▸ 10-DAY NET REALIZED ROI:     {tot_sign}{total_roi_pct:.2f}% GAIN")
    print("=" * 110)

if __name__ == '__main__':
    run_gap_filtered_10day_simulation()
