"""
Realistic 10-Day Sniper Backtest (Strict Realism, Frictions, Fills)
Powered by AngelOne SmartAPI 15-Minute Candles.
"""
import sys
import os
import io
import json
import pandas as pd
from datetime import datetime, timedelta

# Windows UTF-8 console fix
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from angel_data_feed import get_angel_client, load_instrument_map

def run_10_day_sniper_audit():
    smart = get_angel_client()
    imap = load_instrument_map()
    
    universe = [
        'KEI', 'WOCKPHARMA', 'CHENNPETRO', 'GRAPHITE', 'HEG', 
        'DIXON', 'POLYCAB', 'TRENT', 'HAL', 'BEL', 'VEDL', 
        'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'TATASTEEL', 'INFY'
    ]
    
    to_date = datetime.now().strftime('%Y-%m-%d 15:30')
    from_date = (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d 09:15')
    
    print("=" * 110)
    print("🔍 10-DAY REAL-WORLD AUDIT: THE PRO SNIPER STRATEGY (LAST 10 TRADING SESSIONS)")
    print("Rules: 1 Sniper Trade/Day Max | 09:30 AM Breakout | 1:2.5 R:R | ₹50 Brokerage Deducted")
    print("Starting Capital: ₹5,000 (5x MIS Intraday Leverage)")
    print("=" * 110)
    
    stock_data = {}
    for sym in universe:
        if sym not in imap: continue
        tok = imap[sym]['token']
        try:
            res = smart.getCandleData({
                'exchange': 'NSE',
                'symboltoken': tok,
                'interval': 'FIFTEEN_MINUTE',
                'fromdate': from_date,
                'todate': to_date
            })
            if res.get('status') and res.get('data'):
                df = pd.DataFrame(res['data'], columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                df['time'] = pd.to_datetime(df['time'])
                df['date'] = df['time'].dt.date
                df['time_str'] = df['time'].dt.strftime('%H:%M')
                stock_data[sym] = df
        except Exception:
            continue
            
    sample_sym = 'RELIANCE' if 'RELIANCE' in stock_data else list(stock_data.keys())[0]
    all_dates = sorted(stock_data[sample_sym]['date'].unique())[-10:] # Last 10 trading sessions
    
    account_balance = 5000.0
    initial_balance = 5000.0
    brokerage_per_trade = 50.0
    
    trade_logs = []
    
    for d in all_dates:
        day_candidates = []
        for sym, df in stock_data.items():
            day_df = df[df['date'] == d]
            if len(day_df) < 5: continue
            
            c1 = day_df.iloc[0]
            c1_open = float(c1['open'])
            c1_high = float(c1['high'])
            c1_low = float(c1['low'])
            c1_close = float(c1['close'])
            c1_vol = float(c1['volume'])
            
            if c1_open <= 0: continue
            
            vwap = (c1_high + c1_low + c1_close) / 3.0
            range_pct = (c1_high - c1_low) / c1_open * 100.0
            
            # Require minimum 0.8% expansion
            if range_pct >= 0.8:
                if c1_close > c1_open and c1_close >= vwap:
                    risk = round(c1_high - c1_low, 2)
                    if risk > 0 and (risk / c1_high) <= 0.02:
                        day_candidates.append({
                            'symbol': sym, 'direction': 'LONG', 'trigger': c1_high,
                            'sl': c1_low, 'risk': risk, 'vol': c1_vol, 'day_df': day_df
                        })
                elif c1_close < c1_open and c1_close <= vwap:
                    risk = round(c1_high - c1_low, 2)
                    if risk > 0 and (risk / c1_low) <= 0.02:
                        day_candidates.append({
                            'symbol': sym, 'direction': 'SHORT', 'trigger': c1_low,
                            'sl': c1_high, 'risk': risk, 'vol': c1_vol, 'day_df': day_df
                        })
                        
        if not day_candidates:
            trade_logs.append({
                'date': str(d), 'symbol': 'NONE', 'direction': '-', 'entry': 0.0,
                'exit': 0.0, 'outcome': 'NO SETUP (Capital Safe)', 'gross': 0.0,
                'net': 0.0, 'bal': account_balance
            })
            continue
            
        day_candidates.sort(key=lambda x: x['vol'], reverse=True)
        pick = day_candidates[0]
        
        sym, dirn, trigger, sl, risk, day_df = pick['symbol'], pick['direction'], pick['trigger'], pick['sl'], pick['risk'], pick['day_df']
        t1 = round(trigger + 1.5 * risk, 2) if dirn == 'LONG' else round(trigger - 1.5 * risk, 2)
        t2 = round(trigger + 2.5 * risk, 2) if dirn == 'LONG' else round(trigger - 2.5 * risk, 2)
        
        exposure = account_balance * 5.0
        qty = max(1, int(exposure / trigger))
        
        entered = False
        exit_p = 0.0
        outcome = ""
        
        for idx in range(1, len(day_df)):
            bar = day_df.iloc[idx]
            b_h, b_l, b_c = float(bar['high']), float(bar['low']), float(bar['close'])
            
            if not entered and idx <= 4:
                if dirn == 'LONG' and b_h >= trigger:
                    entered = True
                    entry_p = trigger
                elif dirn == 'SHORT' and b_l <= trigger:
                    entered = True
                    entry_p = trigger
                    
            if entered:
                if dirn == 'LONG':
                    if b_h >= t2:
                        outcome = "HIT T2 (+2.5R)"
                        exit_p = t2
                        break
                    elif b_h >= t1:
                        outcome = "HIT T1 (+1.5R)"
                        exit_p = t1
                        sl = entry_p
                    elif b_l <= sl:
                        outcome = "HIT SL (-1.0R)"
                        exit_p = sl
                        break
                else:
                    if b_l <= t2:
                        outcome = "HIT T2 (+2.5R)"
                        exit_p = t2
                        break
                    elif b_l <= t1:
                        outcome = "HIT T1 (+1.5R)"
                        exit_p = t1
                        sl = entry_p
                    elif b_h >= sl:
                        outcome = "HIT SL (-1.0R)"
                        exit_p = sl
                        break
                        
        if not entered:
            trade_logs.append({
                'date': str(d), 'symbol': sym, 'direction': dirn, 'entry': trigger,
                'exit': 0.0, 'outcome': 'NO BREAKOUT (0 Fill - ₹0)', 'gross': 0.0,
                'net': 0.0, 'bal': account_balance
            })
        else:
            if not outcome:
                outcome = "EOD EXIT (03:15 PM)"
                exit_p = float(day_df.iloc[-1]['close'])
                
            gross = round((exit_p - trigger) * qty if dirn == 'LONG' else (trigger - exit_p) * qty, 2)
            net = round(gross - brokerage_per_trade, 2)
            account_balance += net
            trade_logs.append({
                'date': str(d), 'symbol': sym, 'direction': dirn, 'entry': trigger,
                'exit': exit_p, 'outcome': outcome, 'gross': gross,
                'net': net, 'bal': round(account_balance, 2)
            })
            
    header_fmt = "{:<11} | {:<10} | {:<6} | {:<9} | {:<9} | {:<26} | {:<12} | {:<12}"
    print(header_fmt.format("DATE", "STOCK", "SIGNAL", "ENTRY (Rs)", "EXIT (Rs)", "OUTCOME", "NET P&L", "BALANCE"))
    print("-" * 110)
    for t in trade_logs:
        net_str = f"+Rs.{t['net']:.2f}" if t['net'] > 0 else (f"-Rs.{abs(t['net']):.2f}" if t['net'] < 0 else "Rs.0.00")
        row_fmt = "{:<11} | {:<10} | {:<6} | {:<9.2f} | {:<9.2f} | {:<26} | {:<12} | Rs.{:<10,.2f}"
        print(row_fmt.format(t['date'], t['symbol'], t['direction'], t['entry'], t['exit'], t['outcome'], net_str, t['bal']))
    print("=" * 110)
    
    executed = [t for t in trade_logs if 'HIT' in t['outcome'] or 'EOD' in t['outcome']]
    wins = [t for t in executed if t['net'] > 0]
    losses = [t for t in executed if t['net'] < 0]
    total_net = account_balance - initial_balance
    roi = (total_net / initial_balance) * 100.0
    
    print(f"Total Trading Sessions Audited: {len(all_dates)}")
    print(f"Total Trades Taken:             {len(executed)} trades (Only took {len(executed)} trades in 10 days!)")
    print(f"Days Skipped (Zero Risk):       {len(all_dates) - len(executed)} days (Preserved capital when market was bad)")
    print(f"Winning Trades:                 {len(wins)} ({(len(wins)/max(1, len(executed)))*100:.1f}% Win Rate)")
    print(f"Losing Trades:                  {len(losses)}")
    print(f"Total Brokerage Deducted:       Rs.{len(executed) * brokerage_per_trade:,.2f} (Only Rs.{len(executed)*50} total!)")
    print(f"Starting Capital:               Rs.{initial_balance:,.2f}")
    print(f"Ending Balance:                 Rs.{account_balance:,.2f}")
    print(f"NET REALIZED PROFIT/LOSS:       {'+' if total_net >= 0 else '-'}Rs.{abs(total_net):,.2f} ({'+' if roi >= 0 else ''}{roi:.2f}% ROI)")
    print("=" * 110)

if __name__ == '__main__':
    run_10_day_sniper_audit()
