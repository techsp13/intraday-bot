import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
from datetime import datetime

PICKS_TODAY = [
    {'symbol': 'IFCI', 'ticker': 'IFCI.NS', 'direction': 'LONG', 'entry': 98.32, 'sl': 96.35, 't1': 101.28, 't2': 103.24, 'qty_6800': 69, 'qty_1lakh': 1017},
    {'symbol': 'ENGINERSIN', 'ticker': 'ENGINERSIN.NS', 'direction': 'LONG', 'entry': 276.60, 'sl': 271.07, 't1': 284.90, 't2': 290.42, 'qty_6800': 24, 'qty_1lakh': 361},
    {'symbol': 'ATHERENERG', 'ticker': 'ATHERENERG.NS', 'direction': 'LONG', 'entry': 1686.10, 'sl': 1652.38, 't1': 1736.68, 't2': 1770.40, 'qty_6800': 4, 'qty_1lakh': 59},
    {'symbol': 'ZEEL', 'ticker': 'ZEEL.NS', 'direction': 'SHORT', 'entry': 90.57, 'sl': 92.38, 't1': 87.85, 't2': 86.04, 'qty_6800': 75, 'qty_1lakh': 1104},
    {'symbol': 'KAYNES', 'ticker': 'KAYNES.NS', 'direction': 'SHORT', 'entry': 3583.00, 'sl': 3654.66, 't1': 3475.51, 't2': 3403.85, 'qty_6800': 1, 'qty_1lakh': 27}
]

def calculate_today_report():
    print("=" * 95)
    print("📊 OFFICIAL INTRADAY P&L REPORT — MONDAY, 07-SEP-2026")
    print("=" * 95)

    total_pnl_6800 = 0.0
    total_pnl_1lakh = 0.0

    print(f"{'Stock':<12} | {'Type':<6} | {'Entry':<8} | {'Day Low':<8} | {'Day High':<8} | {'Exit':<8} | {'Outcome':<22} | {'P&L (₹6,800)':<12} | P&L (₹1 Lakh)")
    print("-" * 105)

    for p in PICKS_TODAY:
        sym = p['symbol']
        ticker = p['ticker']
        dirn = p['direction']
        entry = p['entry']
        sl = p['sl']
        t1 = p['t1']
        t2 = p['t2']
        q_6800 = p['qty_6800']
        q_1lakh = p['qty_1lakh']

        try:
            df = yf.download(ticker, period="5d", interval="5m", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
            
            today_df = df[df.index.date == df.index.date[-1]]
            if not today_df.empty:
                day_open = float(today_df.iloc[0]['Open'])
                day_high = float(today_df['High'].max())
                day_low = float(today_df['Low'].min())
                day_close = float(today_df.iloc[-1]['Close'])
            else:
                day_high, day_low, day_close = entry, entry, entry
        except Exception:
            day_high, day_low, day_close = entry, entry, entry

        if dirn == 'LONG':
            if day_high >= t2:
                outcome = "🎯 Hit Target 2 (+5%)"
                exit_price = t2
            elif day_high >= t1:
                outcome = "🎯 Hit Target 1 (+3%)"
                exit_price = t1
            elif day_low <= sl:
                outcome = "🛑 Hit Stop Loss (-2%)"
                exit_price = sl
            else:
                outcome = "⏱️ Square-off (03:15 PM)"
                exit_price = day_close
            pnl_6800 = (exit_price - entry) * q_6800
            pnl_1lakh = (exit_price - entry) * q_1lakh
        else: # SHORT
            if day_low <= t2:
                outcome = "🎯 Hit Target 2 (+5%)"
                exit_price = t2
            elif day_low <= t1:
                outcome = "🎯 Hit Target 1 (+3%)"
                exit_price = t1
            elif day_high >= sl:
                outcome = "🛑 Hit Stop Loss (-2%)"
                exit_price = sl
            else:
                outcome = "⏱️ Square-off (03:15 PM)"
                exit_price = day_close
            pnl_6800 = (entry - exit_price) * q_6800
            pnl_1lakh = (entry - exit_price) * q_1lakh

        total_pnl_6800 += pnl_6800
        total_pnl_1lakh += pnl_1lakh

        s_6800 = f"+₹{pnl_6800:,.2f}" if pnl_6800 >= 0 else f"-₹{abs(pnl_6800):,.2f}"
        s_1lakh = f"+₹{pnl_1lakh:,.2f}" if pnl_1lakh >= 0 else f"-₹{abs(pnl_1lakh):,.2f}"

        print(f"{sym:<12} | {dirn:<6} | ₹{entry:>7.2f} | ₹{day_low:>7.2f} | ₹{day_high:>7.2f} | ₹{exit_price:>7.2f} | {outcome:<22} | {s_6800:>12} | {s_1lakh:>14}")

    print("=" * 105)
    sign_6800 = "+" if total_pnl_6800 >= 0 else ""
    sign_1lakh = "+" if total_pnl_1lakh >= 0 else ""
    print(f"💰 TOTAL REALIZED NET P&L (₹6,800 Starting Demat Capital): {sign_6800}₹{total_pnl_6800:,.2f}")
    print(f"💰 TOTAL REALIZED NET P&L (₹1,00,000 Demat Capital):       {sign_1lakh}₹{total_pnl_1lakh:,.2f}")
    print("=" * 105)

if __name__ == '__main__':
    calculate_today_report()
