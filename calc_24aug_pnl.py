import yfinance as yf
import pandas as pd

picks = [
    {'symbol': 'WELCORP', 'ticker': 'WELCORP.NS', 'direction': 'LONG', 'entry': 2364.10, 'sl': 2316.82, 't1': 2435.02, 't2': 2482.30, 'qty': 8},
    {'symbol': 'URBANCO', 'ticker': 'URBANCO.NS', 'direction': 'LONG', 'entry': 168.39, 'sl': 165.02, 't1': 173.44, 't2': 176.82, 'qty': 118},
    {'symbol': 'WELSPUNLIV', 'ticker': 'WELSPUNLIV.NS', 'direction': 'LONG', 'entry': 192.26, 'sl': 188.41, 't1': 198.04, 't2': 201.88, 'qty': 104},
    {'symbol': 'HSCL', 'ticker': 'HSCL.NS', 'direction': 'SHORT', 'entry': 677.75, 'sl': 691.30, 't1': 657.42, 't2': 643.88, 'qty': 29},
    {'symbol': 'ASTERDM', 'ticker': 'ASTERDM.NS', 'direction': 'SHORT', 'entry': 763.05, 'sl': 778.31, 't1': 740.16, 't2': 724.90, 'qty': 26},
]

print("=== TODAY'S (24-AUG-2026) INTRADAY TRADE PERFORMANCE ===\n")
total_pnl = 0.0

for p in picks:
    ticker = p['ticker']
    df = yf.download(ticker, period='5d', interval='5m', progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
    
    today_df = df[df.index.date == df.index.date[-1]]
    if today_df.empty:
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
    print(f"Stock: {p['symbol']:<11} ({direction:<5}) | Qty: {qty:>3} | Entry: Rs.{entry:>8.2f}")
    print(f"  Day Low: Rs.{day_low:>8.2f} | Day High: Rs.{day_high:>8.2f} | Day Close: Rs.{day_close:>8.2f}")
    print(f"  Outcome: {outcome} | Exit: Rs.{exit_price:>8.2f} | PnL: {pnl_sign}Rs.{pnl:,.2f}")
    print("-" * 65)

total_sign = "+" if total_pnl >= 0 else ""
print(f"\nTOTAL TODAY'S (24-AUG-2026) NET P&L: {total_sign}Rs.{total_pnl:,.2f}")
