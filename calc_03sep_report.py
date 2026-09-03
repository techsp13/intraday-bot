import yfinance as yf
import pandas as pd

picks = [
    {'symbol': 'IFCI', 'ticker': 'IFCI.NS', 'direction': 'LONG', 'entry': 98.32, 'sl': 96.35, 't1': 101.28, 't2': 103.24, 'qty': 203},
    {'symbol': 'ZEEL', 'ticker': 'ZEEL.NS', 'direction': 'SHORT', 'entry': 90.57, 'sl': 92.38, 't1': 87.85, 't2': 86.04, 'qty': 220},
    {'symbol': 'ATHERENERG', 'ticker': 'ATHERENERG.NS', 'direction': 'LONG', 'entry': 1686.10, 'sl': 1652.38, 't1': 1736.68, 't2': 1770.40, 'qty': 11},
    {'symbol': 'ENGINERSIN', 'ticker': 'ENGINERSIN.NS', 'direction': 'LONG', 'entry': 276.60, 'sl': 271.07, 't1': 284.90, 't2': 290.42, 'qty': 72},
    {'symbol': 'KAYNES', 'ticker': 'KAYNES.NS', 'direction': 'SHORT', 'entry': 3583.00, 'sl': 3654.66, 't1': 3475.51, 't2': 3403.85, 'qty': 5},
]

print("=== INTRADAY REPORT FOR TODAY (03-SEP-2026) ===\n")
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
