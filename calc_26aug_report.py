import yfinance as yf
import pandas as pd

picks = [
    {'symbol': 'CYIENT', 'ticker': 'CYIENT.NS', 'direction': 'LONG', 'entry': 1045.20, 'sl': 1024.30, 't1': 1076.55, 't2': 1097.45, 'qty': 19},
    {'symbol': 'HSCL', 'ticker': 'HSCL.NS', 'direction': 'SHORT', 'entry': 663.85, 'sl': 677.13, 't1': 643.93, 't2': 630.65, 'qty': 30},
]

print("=== INTRADAY REPORT FOR TODAY (26-AUG-2026) ===\n")
total_pnl = 0.0

for p in picks:
    ticker = p['ticker']
    df = yf.download(ticker, period='5d', interval='5m', progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
    
    today_df = df[df.index.date == df.index.date[-1]]
    if today_df.empty:
        print(f"No data found for {ticker}")
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
        
    total_pnl += pnl
    pnl_sign = "+" if pnl >= 0 else ""
    print(f"Stock: {p['symbol']:<10} ({direction:<5}) | Qty: {qty:>2} | Entry: Rs.{entry:>7.2f}")
    print(f"  Day Range: Low Rs.{day_low:>7.2f} / High Rs.{day_high:>7.2f} / Close Rs.{day_close:>7.2f}")
    print(f"  Outcome:   {outcome} | Exit: Rs.{exit_price:>7.2f} | Net PnL: {pnl_sign}Rs.{pnl:,.2f}")
    print("-" * 65)

total_sign = "+" if total_pnl >= 0 else ""
print(f"\nTOTAL TODAY'S (26-AUG-2026) NET P&L: {total_sign}Rs.{total_pnl:,.2f}")
