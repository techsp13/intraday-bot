import yfinance as yf
import pandas as pd

picks = [
    {'symbol': 'WELSPUNLIV', 'ticker': 'WELSPUNLIV.NS', 'entry': 177.79, 'sl': 174.23, 't1': 183.13, 't2': 186.69, 'qty': 112},
    {'symbol': 'NETWEB', 'ticker': 'NETWEB.NS', 'entry': 5354.50, 'sl': 5247.41, 't1': 5515.14, 't2': 5622.22, 'qty': 3},
]

print("=== TODAY'S (19-AUG-2026) INTRADAY TRADE PERFORMANCE ===\n")
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
        
    day_open = today_df.iloc[0]['Open']
    day_high = today_df['High'].max()
    day_low = today_df['Low'].min()
    day_close = today_df.iloc[-1]['Close']
    
    entry = p['entry']
    sl = p['sl']
    t1 = p['t1']
    t2 = p['t2']
    qty = p['qty']
    
    if day_high >= t2:
        outcome = "HIT_T2 (+5.0%)"
        exit_price = t2
    elif day_high >= t1:
        outcome = "HIT_T1 (+3.0%)"
        exit_price = t1
    elif day_low <= sl:
        outcome = "HIT_SL (-2.0%)"
        exit_price = sl
    else:
        outcome = "CLOSED_3:15PM"
        exit_price = day_close
        
    pnl = (exit_price - entry) * qty
    total_pnl += pnl
    
    pnl_sign = "+" if pnl >= 0 else ""
    print(f"Stock: {p['symbol']:<11} | Qty: {qty:>3} | Entry: Rs.{entry:>8.2f}")
    print(f"  Day Low: Rs.{day_low:>8.2f} | Day High: Rs.{day_high:>8.2f} | Day Close: Rs.{day_close:>8.2f}")
    print(f"  Outcome: {outcome} | Exit: Rs.{exit_price:>8.2f} | PnL: {pnl_sign}Rs.{pnl:,.2f}")
    print("-" * 62)

total_sign = "+" if total_pnl >= 0 else ""
print(f"\nTOTAL TODAY'S (19-AUG-2026) NET P&L: {total_sign}Rs.{total_pnl:,.2f}")
