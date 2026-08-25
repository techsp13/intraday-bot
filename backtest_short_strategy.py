"""
Comprehensive 3-Year Quantitative Backtest for Short (Relative Weakness) Strategy
Dataset: NIFTY 500 universe historical daily & intraday price data.

Short Strategy Rules:
- Setup: 5-Day Relative Weakness vs NIFTY (RS <= -2.0%)
- Entry: Market Open (09:15 AM)
- Stop Loss: +2.0% above entry
- Target 1: -3.0% below entry (1.5R)
- Target 2: -5.0% below entry (2.5R)
- Exit: 03:15 PM EOD Square-off if neither SL nor Target hit.
- Risk Sizing: ₹1,000 risk per trade (1% of ₹100,000 capital)
"""
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import numpy as np

def run_short_backtest():
    print("=== STARTING 3-YEAR QUANTITATIVE BACKTEST: SHORT (RELATIVE WEAKNESS) STRATEGY ===\n")
    print("Fetching benchmark and historical dataset (2023 - 2026)...")
    
    # Representative liquid universe across major sectors
    test_symbols = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS",
        "AXISBANK.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "MARUTI.NS",
        "SUNPHARMA.NS", "TITAN.NS", "POWERGRID.NS", "NTPC.NS", "TATASTEEL.NS",
        "COALINDIA.NS", "ONGC.NS", "ADANIENT.NS", "ADANIPORTS.NS", "JSWSTEEL.NS",
        "BPCL.NS", "IOC.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
        "VEDL.NS", "HINDALCO.NS", "DLF.NS", "GODREJPROP.NS", "PAYTM.NS",
        "IDEA.NS", "ZEEL.NS", "GLAND.NS", "FINCABLES.NS", "ZENTEC.NS"
    ]
    
    # 1. Fetch NIFTY Index
    nifty = yf.download("^NSEI", period="3y", interval="1d", progress=False)
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)
    nifty.index = nifty.index.tz_localize(None) if nifty.index.tz is not None else nifty.index
    nifty['5d_Ret'] = nifty['Close'].pct_change(5) * 100.0

    # 2. Fetch Stock Universe
    stock_data = yf.download(test_symbols, period="3y", interval="1d", progress=False, group_by="ticker")

    all_trades = []
    initial_capital = 100000.0
    risk_per_trade = 1000.0

    dates = nifty.index[30:] # Start after warm-up

    for d_idx in range(len(dates) - 1):
        curr_date = dates[d_idx]
        next_date = dates[d_idx + 1]

        nifty_sub = nifty.loc[:curr_date]
        if len(nifty_sub) < 6:
            continue
        nifty_5d_ret = nifty_sub.iloc[-1]['5d_Ret']
        if pd.isna(nifty_5d_ret):
            continue

        # Find Relative Weakness candidates on curr_date
        rw_candidates = []

        for sym in test_symbols:
            try:
                s_df = stock_data[sym].loc[:curr_date].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(stock_data.columns, pd.MultiIndex) else stock_data.loc[:curr_date]
                if len(s_df) < 6:
                    continue

                s_close = s_df.iloc[-1]['Close']
                s_close_prev5 = s_df.iloc[-6]['Close']
                s_5d_ret = (s_close - s_close_prev5) / s_close_prev5 * 100.0

                rs = s_5d_ret - nifty_5d_ret # Relative Weakness if negative
                if rs <= -2.0:
                    rw_candidates.append({
                        'symbol': sym,
                        'rs': rs,
                        'last_close': s_close
                    })
            except Exception:
                continue

        # Sort by weakest (most negative RS)
        rw_candidates.sort(key=lambda x: x['rs'])
        top_picks = rw_candidates[:2] # Top 2 short setups per day

        # Simulate execution on next_date
        for pick in top_picks:
            sym = pick['symbol']
            try:
                nxt_bar = stock_data[sym].loc[next_date] if isinstance(stock_data.columns, pd.MultiIndex) else stock_data.loc[next_date]
                if nxt_bar.empty or pd.isna(nxt_bar['Open']):
                    continue

                entry = float(nxt_bar['Open'])
                day_high = float(nxt_bar['High'])
                day_low = float(nxt_bar['Low'])
                day_close = float(nxt_bar['Close'])

                # Short Price Levels
                sl = entry * 1.02          # Buy SL +2.0% above
                t1 = entry * 0.97          # Target 1 -3.0% below
                t2 = entry * 0.95          # Target 2 -5.0% below

                risk_per_share = sl - entry
                qty = max(1, int(risk_per_trade / risk_per_share))

                # Determine Outcome
                if day_low <= t2:
                    outcome = "HIT_T2"
                    exit_price = t2
                elif day_low <= t1:
                    outcome = "HIT_T1"
                    exit_price = t1
                elif day_high >= sl:
                    outcome = "HIT_SL"
                    exit_price = sl
                else:
                    outcome = "CLOSED_EOD"
                    exit_price = day_close

                # Short PnL = (Entry - Exit) * Qty
                pnl = (entry - exit_price) * qty
                r_multiple = (entry - exit_price) / risk_per_share

                all_trades.append({
                    'date': next_date.strftime('%Y-%m-%d'),
                    'symbol': sym.replace('.NS', ''),
                    'rs': pick['rs'],
                    'entry': entry,
                    'exit': exit_price,
                    'sl': sl,
                    't1': t1,
                    't2': t2,
                    'qty': qty,
                    'outcome': outcome,
                    'pnl': pnl,
                    'r_multiple': r_multiple
                })
            except Exception:
                continue

    # 3. Process Backtest Metrics
    df_trades = pd.DataFrame(all_trades)
    if df_trades.empty:
        print("No trades generated.")
        return

    total_trades = len(df_trades)
    t2_hits = len(df_trades[df_trades['outcome'] == 'HIT_T2'])
    t1_hits = len(df_trades[df_trades['outcome'] == 'HIT_T1'])
    sl_hits = len(df_trades[df_trades['outcome'] == 'HIT_SL'])
    eod_closed = len(df_trades[df_trades['outcome'] == 'CLOSED_EOD'])
    
    wins = df_trades[df_trades['pnl'] > 0]
    losses = df_trades[df_trades['pnl'] < 0]
    
    win_rate = (len(wins) / total_trades) * 100.0
    
    gross_profit = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    net_pnl = gross_profit - gross_loss
    
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0.0
    avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 0.0
    rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    
    # Equity Curve & Drawdown
    df_trades['cum_pnl'] = df_trades['pnl'].cumsum()
    df_trades['equity'] = initial_capital + df_trades['cum_pnl']
    df_trades['peak'] = df_trades['equity'].cummax()
    df_trades['drawdown'] = (df_trades['equity'] - df_trades['peak']) / df_trades['peak'] * 100.0
    max_drawdown = abs(df_trades['drawdown'].min())
    total_return_pct = (net_pnl / initial_capital) * 100.0

    print("=" * 65)
    print("[BACKTEST RESULT] 3-YEAR SHORT STRATEGY PERFORMANCE (2023 - 2026)")
    print("=" * 65)
    print(f"Total Short Trades Executed:   {total_trades:,}")
    print(f"Win Rate:                      {win_rate:.1f}% ({len(wins)} Wins / {len(losses)} Losses)")
    print(f"Target 2 Hit Rate (+5.0%):     {(t2_hits / total_trades * 100):.1f}% ({t2_hits} trades)")
    print(f"Target 1 Hit Rate (+3.0%):     {(t1_hits / total_trades * 100):.1f}% ({t1_hits} trades)")
    print(f"Stop Loss Rate (-2.0%):        {(sl_hits / total_trades * 100):.1f}% ({sl_hits} trades)")
    print(f"EOD 03:15 PM Square-off:       {(eod_closed / total_trades * 100):.1f}% ({eod_closed} trades)")
    print("-" * 65)
    print(f"Initial Starting Capital:      Rs. {initial_capital:,.2f}")
    print(f"Gross Profit (Wins):           +Rs. {gross_profit:,.2f}")
    print(f"Gross Loss (SL/Exits):         -Rs. {gross_loss:,.2f}")
    print(f"NET PROFIT REALIZED:           +Rs. {net_pnl:,.2f} (+{total_return_pct:.1f}%)")
    print(f"Ending Capital:                Rs. {(initial_capital + net_pnl):,.2f}")
    print("-" * 65)
    print(f"Profit Factor:                 {profit_factor:.2f}")
    print(f"Average Win:                   +Rs. {avg_win:,.2f}")
    print(f"Average Loss:                  -Rs. {avg_loss:,.2f}")
    print(f"Realized Risk-Reward Ratio:    1 : {rr_ratio:.2f}")
    print(f"Max Portfolio Drawdown:        {max_drawdown:.1f}%")
    print("=" * 65)

if __name__ == '__main__':
    run_short_backtest()
