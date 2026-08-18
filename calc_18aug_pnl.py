import yfinance as yf
import pandas as pd

morning_picks = [
    {'symbol': 'FINCABLES', 'ticker': 'FINCABLES.NS', 'entry': 1320.85, 'sl': 1294.43, 't1': 1360.48, 't2': 1386.90, 'qty': 15},
    {'symbol': 'ZENTEC', 'ticker': 'ZENTEC.NS', 'entry': 1864.50, 'sl': 1827.21, 't1': 1920.44, 't2': 1957.72, 'qty': 10},
    {'symbol': 'BATAINDIA', 'ticker': 'BATAINDIA.NS', 'entry': 758.10, 'sl': 742.94, 't1': 780.84, 't2': 796.00, 'qty': 26},
    {'symbol': 'GLAND', 'ticker': 'GLAND.NS', 'entry': 2910.20, 'sl': 2852.00, 't1': 2997.50, 't2': 3055.70, 'qty': 6},
    {'symbol': 'WELSPUNLIV', 'ticker': 'WELSPUNLIV.NS', 'entry': 179.78, 'sl': 176.18, 't1': 185.18, 't2': 188.78, 'qty': 111},
    {'symbol': 'ZEEL', 'ticker': 'ZEEL.NS', 'entry': 103.88, 'sl': 101.80, 't1': 107.00, 't2': 109.08, 'qty': 192},
]

print("=== TODAY'S (18-AUG-2026) INTRADAY TRADE PERFORMANCE ===\n")
total_pnl = 0.0

for p in morning_picks:
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
    trade_date = today_df.index[-1].strftime('%d-%b-%Y')
    
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
    print(f"Stock: {p['symbol']:<11} | Qty: {qty:>3} | Entry: Rs.{entry:>7.2f}")
    print(f"  Day Low: Rs.{day_low:>7.2f} | Day High: Rs.{day_high:>7.2f} | Day Close: Rs.{day_close:>7.2f}")
    print(f"  Outcome: {outcome} | Exit: Rs.{exit_price:>7.2f} | PnL: {pnl_sign}Rs.{pnl:,.2f}")
    print("-" * 62)

total_sign = "+" if total_pnl >= 0 else ""
print(f"\nTOTAL TODAY'S (18-AUG-2026) NET P&L: {total_sign}Rs.{total_pnl:,.2f}")
