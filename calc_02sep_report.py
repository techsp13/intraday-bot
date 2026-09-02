import yfinance as yf
import pandas as pd

picks = [
    {'symbol': 'CYIENT', 'ticker': 'CYIENT.NS', 'direction': 'LONG', 'entry': 1174.80, 'sl': 1151.30, 't1': 1210.05, 't2': 1233.55, 'qty': 17},
    {'symbol': 'ADANIENSOL', 'ticker': 'ADANIENSOL.NS', 'direction': 'SHORT', 'entry': 1382.00, 'sl': 1409.64, 't1': 1340.54, 't2': 1312.90, 'qty': 14},
    {'symbol': 'ATHERENERG', 'ticker': 'ATHERENERG.NS', 'direction': 'LONG', 'entry': 1725.60, 'sl': 1691.09, 't1': 1777.36, 't2': 1811.88, 'qty': 11},
    {'symbol': 'NSLNISP', 'ticker': 'NSLNISP.NS', 'direction': 'LONG', 'entry': 45.61, 'sl': 44.70, 't1': 46.98, 't2': 47.88, 'qty': 438},
    {'symbol': 'ZEEL', 'ticker': 'ZEEL.NS', 'direction': 'SHORT', 'entry': 93.41, 'sl': 95.28, 't1': 90.60, 't2': 88.74, 'qty': 214},
]

print("=== INTRADAY REPORT FOR TODAY (02-SEP-2026) ===\n")
total_top2_pnl = 0.0
total_all_pnl = 0.0

for i, p in enumerate(picks, 1):
    ticker = p['ticker']
    try:
        df = yf.download(ticker, period='5d', interval='5m', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        
        today_df = df[df.index.date == df.index.date[-1]]
        if today_df.empty:
            print(f"No data for {ticker}")
            continue
            
        day_open = round(float(today_df.iloc[0]['Open']), 2)
        day_high = round(float(today_df['High'].max()), 2)
        day_low = round(float(today_df['Low'].min()), 2)
        day_close = round(float(today_df.iloc[-1]['Close']), 2)
        
        entry = p['entry']
        sl = p['sl']
        t1 = p['t1']
        t2 = p['t2']
        qty = p['qty']
        direction = p['direction']
        
        if direction == 'LONG':
            if day_high >= t2:
                outcome = "HIT TARGET 2 (+5.0%)"
                exit_price = t2
            elif day_high >= t1:
                outcome = "HIT TARGET 1 (+3.0%)"
                exit_price = t1
            elif day_low <= sl:
                outcome = "HIT STOP LOSS (-2.0%)"
                exit_price = sl
            else:
                outcome = "CLOSED AT 03:15 PM"
                exit_price = day_close
            pnl = round((exit_price - entry) * qty, 2)
        else: # SHORT
            if day_low <= t2:
                outcome = "HIT TARGET 2 (+5.0%)"
                exit_price = t2
            elif day_low <= t1:
                outcome = "HIT TARGET 1 (+3.0%)"
                exit_price = t1
            elif day_high >= sl:
                outcome = "HIT STOP LOSS (-2.0%)"
                exit_price = sl
            else:
                outcome = "CLOSED AT 03:15 PM"
                exit_price = day_close
            pnl = round((entry - exit_price) * qty, 2)
            
        if i <= 2:
            total_top2_pnl += pnl
        total_all_pnl += pnl
        
        pnl_sign = "+" if pnl >= 0 else ""
        badge = "[TOP 2]" if i <= 2 else "[WATCHLIST]"
        print(f"{badge} {p['symbol']:<11} ({direction:<5}) | Qty: {qty:>3} | Entry: Rs.{entry:>7.2f}")
        print(f"   Day Range: Low Rs.{day_low:>7.2f} / High Rs.{day_high:>7.2f} / Close Rs.{day_close:>7.2f}")
        print(f"   Outcome:   {outcome} | Exit: Rs.{exit_price:>7.2f} | Net PnL: {pnl_sign}Rs.{pnl:,.2f}")
        print("-" * 68)
    except Exception as e:
        print(f"Error evaluating {p['symbol']}: {e}")

top2_sign = "+" if total_top2_pnl >= 0 else ""
all_sign = "+" if total_all_pnl >= 0 else ""
print(f"\nTOP 2 PICKS REALIZED NET P&L: {top2_sign}Rs.{total_top2_pnl:,.2f}")
print(f"ALL 5 STOCKS REALIZED NET P&L: {all_sign}Rs.{total_all_pnl:,.2f}")
