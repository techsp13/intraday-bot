import yfinance as yf
import pandas as pd

picks = [
    {'symbol': 'JYOTICNC', 'ticker': 'JYOTICNC.NS', 'entry': 950.65, 'sl': 931.64, 't1': 979.17, 't2': 998.18, 'qty': 21},
    {'symbol': 'IFCI', 'ticker': 'IFCI.NS', 'entry': 81.68, 'sl': 80.05, 't1': 84.13, 't2': 85.76, 'qty': 244},
    {'symbol': 'ACE', 'ticker': 'ACE.NS', 'entry': 1184.80, 'sl': 1161.10, 't1': 1220.35, 't2': 1244.05, 'qty': 16},
    {'symbol': 'WELSPUNLIV', 'ticker': 'WELSPUNLIV.NS', 'entry': 181.24, 'sl': 177.62, 't1': 186.67, 't2': 189.92, 'qty': 110},
    {'symbol': 'ZENTEC', 'ticker': 'ZENTEC.NS', 'entry': 1982.40, 'sl': 1942.75, 't1': 2041.87, 't2': 2081.52, 'qty': 10},
]

print("=== TODAY'S (20-AUG-2026) INTRADAY TRADE PERFORMANCE ===\n")
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
    total_pnl += pnl
    
    pnl_sign = "+" if pnl >= 0 else ""
    print(f"Stock: {p['symbol']:<11} | Qty: {qty:>3} | Entry: Rs.{entry:>8.2f}")
    print(f"  Day Low: Rs.{day_low:>8.2f} | Day High: Rs.{day_high:>8.2f} | Day Close: Rs.{day_close:>8.2f}")
    print(f"  Outcome: {outcome} | Exit: Rs.{exit_price:>8.2f} | PnL: {pnl_sign}Rs.{pnl:,.2f}")
    print("-" * 62)

total_sign = "+" if total_pnl >= 0 else ""
print(f"\nTOTAL TODAY'S (20-AUG-2026) NET P&L: {total_sign}Rs.{total_pnl:,.2f}")
