"""
STG2 Full Trading Hours Live Monitor (09:15 AM to 03:30 PM IST)
Powered by AngelOne SmartAPI.

Monitors active STG2 trades in real-time:
1. 09:30 AM: Triggers STG2 sniper scan and sends morning entry alert.
2. 09:30 - 03:15 PM: Polls live LTP from AngelOne every 30 seconds.
3. Automatically alerts when:
   - Target 1 is hit (+1.5R): "Book 50% profit & trail SL to Cost!"
   - Target 2 is hit (+2.5R): "Target 2 achieved! Complete exit."
   - Stop Loss is hit: "Cut trade immediately!"
   - 03:15 PM: Mandatory square-off alert.
"""
import sys
import os
import io
import time
import json
from datetime import datetime, time as dtime

# Windows UTF-8 console fix
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
import alerts
from angel_data_feed import get_angel_client, get_live_quote
from screener_stg2 import scan_stg2

ACTIVE_TRADES_FILE = os.path.join(config.DATA_DIR, "active_stg2_trades.json")

def load_active_trades():
    if os.path.exists(ACTIVE_TRADES_FILE):
        try:
            with open(ACTIVE_TRADES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_active_trades(trades):
    with open(ACTIVE_TRADES_FILE, 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=2)

def is_trading_day():
    weekday = datetime.now().weekday()
    return weekday < 5 # 0=Mon, 4=Fri

def monitor_live_session(dry_run: bool = False):
    print("==========================================================")
    print("🚀 STG2 FULL-DAY LIVE TRADING MONITOR STARTED")
    print(f"Time: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')} IST")
    print(f"Broker Engine: AngelOne SmartAPI (Live Level-2 Depth)")
    print(f"Dry Run Mode: {dry_run}")
    print("==========================================================\n")
    
    scan_completed_today = False
    
    while True:
        now = datetime.now()
        current_time = now.time()
        
        # 1. Weekend Check
        if not is_trading_day() and not dry_run:
            print(f"Market Closed: Today is weekend ({now.strftime('%A')}). Sleeping 60s...")
            time.sleep(60)
            continue
            
        # 2. Before 09:15 AM Pre-market
        if current_time < dtime(9, 15) and not dry_run:
            wait_secs = (datetime.combine(now.date(), dtime(9, 15)) - now).total_seconds()
            print(f"Market opens at 09:15 AM. Waiting {int(wait_secs)} seconds...")
            time.sleep(min(60, max(5, wait_secs)))
            continue
            
        # 3. 09:15 to 09:30 AM (Opening Noise / Let institutions dump)
        if dtime(9, 15) <= current_time < dtime(9, 30) and not dry_run:
            print(f"[{now.strftime('%H:%M:%S')}] Hands-off Window (09:15 - 09:30 AM). Letting opening volatility settle...")
            time.sleep(30)
            continue
            
        # 4. 09:30 AM: Trigger STG2 Sniper Scan
        if dtime(9, 30) <= current_time < dtime(10, 15) and not scan_completed_today:
            print(f"\n[{now.strftime('%H:%M:%S')}] ⏰ 09:30 AM TRIGGER! Running STG2 AngelOne Depth Scan...")
            picks = scan_stg2(max_picks=2)
            
            if picks:
                print(f"Identified {len(picks)} high-conviction sniper picks.")
                active_list = []
                for p in picks:
                    active_list.append({
                        'symbol': p['symbol'],
                        'direction': p['direction'],
                        'entry': p['entry'],
                        'sl': p['sl'],
                        'target1': p['target1'],
                        'target2': p['target2'],
                        't1_hit': False,
                        't2_hit': False,
                        'sl_hit': False,
                        'entry_time': now.strftime('%H:%M:%S')
                    })
                save_active_trades(active_list)
                
                # Send Morning Telegram Alert
                date_str = now.strftime("%d-%b-%Y")
                msg = f"🎯 *STG2: 15-MIN ORB + VWAP SNIPER — {date_str} (09:30 AM)*\n"
                msg += f"▸ *Live Market Depth & Buyer Dominance Confirmed*\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━━\n"
                for i, p in enumerate(picks, 1):
                    badge = "🟢 LONG (BUY)" if p["direction"] == "LONG" else "🔴 SHORT (SELL)"
                    msg += f"*{i}️⃣ {p['symbol']}* — {badge}\n"
                    msg += f"▸ Entry: `₹{p['entry']:,.2f}` | SL: `₹{p['sl']:,.2f}`\n"
                    msg += f"▸ T1: `₹{p['target1']:,.2f}` (+1.5R) | T2: `₹{p['target2']:,.2f}` (+2.5R)\n"
                    msg += f"▸ Order Book: *{p['buy_qty']:,} Buyers* vs *{p['sell_qty']:,} Sellers*\n\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━━\n"
                msg += "🤖 *Live Monitoring Active*: You will receive instant alerts on T1, T2 & SL."
                
                if not dry_run:
                    alerts.send_telegram_message(msg)
                print(msg)
            else:
                print("No stocks met strict STG2 criteria today. Capital 100% protected.")
                
            scan_completed_today = True
            
        # 5. Continuous Live Tracking (09:30 AM - 03:15 PM)
        active_trades = load_active_trades()
        if active_trades and (current_time < dtime(15, 15) or dry_run):
            for t in active_trades:
                if t['sl_hit'] or t['t2_hit']:
                    continue # Trade already closed
                    
                sym = t['symbol']
                dirn = t['direction']
                quote = get_live_quote(sym)
                ltp = float(quote.get('ltp', 0.0))
                
                if ltp <= 0:
                    continue
                    
                # Check LONG exits
                if dirn == 'LONG':
                    if ltp >= t['target2'] and not t['t2_hit']:
                        t['t2_hit'] = True
                        alert_msg = f"🎉 *TARGET 2 HIT on {sym}!* (+2.5R)\n▸ Current Price: `₹{ltp:,.2f}` (Target: `₹{t['target2']:,.2f}`)\n▸ *Action*: Complete exit! Full profit booked! 💰"
                        print(alert_msg)
                        if not dry_run: alerts.send_telegram_message(alert_msg)
                    elif ltp >= t['target1'] and not t['t1_hit']:
                        t['t1_hit'] = True
                        t['sl'] = t['entry'] # Trail SL to entry
                        alert_msg = f"🎯 *TARGET 1 HIT on {sym}!* (+1.5R)\n▸ Current Price: `₹{ltp:,.2f}`\n▸ *Action*: Book 50% profit now!\n▸ *Risk Free*: Trailing Stop Loss moved to Entry (`₹{t['entry']:,.2f}`)."
                        print(alert_msg)
                        if not dry_run: alerts.send_telegram_message(alert_msg)
                    elif ltp <= t['sl'] and not t['sl_hit']:
                        t['sl_hit'] = True
                        alert_msg = f"⚠️ *STOP LOSS HIT on {sym}!*\n▸ Current Price: `₹{ltp:,.2f}` (SL: `₹{t['sl']:,.2f}`)\n▸ *Action*: Cut trade immediately. Protect capital."
                        print(alert_msg)
                        if not dry_run: alerts.send_telegram_message(alert_msg)
                        
                # Check SHORT exits
                elif dirn == 'SHORT':
                    if ltp <= t['target2'] and not t['t2_hit']:
                        t['t2_hit'] = True
                        alert_msg = f"🎉 *TARGET 2 HIT on {sym}!* (+2.5R)\n▸ Current Price: `₹{ltp:,.2f}` (Target: `₹{t['target2']:,.2f}`)\n▸ *Action*: Buy back to cover! Full profit booked! 💰"
                        print(alert_msg)
                        if not dry_run: alerts.send_telegram_message(alert_msg)
                    elif ltp <= t['target1'] and not t['t1_hit']:
                        t['t1_hit'] = True
                        t['sl'] = t['entry']
                        alert_msg = f"🎯 *TARGET 1 HIT on {sym}!* (+1.5R)\n▸ Current Price: `₹{ltp:,.2f}`\n▸ *Action*: Book 50% profit now!\n▸ *Risk Free*: Trailing Stop Loss moved to Entry (`₹{t['entry']:,.2f}`)."
                        print(alert_msg)
                        if not dry_run: alerts.send_telegram_message(alert_msg)
                    elif ltp >= t['sl'] and not t['sl_hit']:
                        t['sl_hit'] = True
                        alert_msg = f"⚠️ *STOP LOSS HIT on {sym}!*\n▸ Current Price: `₹{ltp:,.2f}` (SL: `₹{t['sl']:,.2f}`)\n▸ *Action*: Cut short trade immediately. Protect capital."
                        print(alert_msg)
                        if not dry_run: alerts.send_telegram_message(alert_msg)
                        
            save_active_trades(active_trades)
            
        # 6. 03:15 PM: Mandatory Square-off Alert
        if dtime(15, 15) <= current_time < dtime(15, 20) and not dry_run:
            open_trades = [t['symbol'] for t in load_active_trades() if not t['sl_hit'] and not t['t2_hit']]
            if open_trades:
                msg = f"⏰ *03:15 PM MANDATORY SQUARE-OFF REMINDER*\nMarket closes soon. Close all open intraday positions: {', '.join(open_trades)}."
                alerts.send_telegram_message(msg)
                save_active_trades([]) # Clear for tomorrow
            time.sleep(300)
            
        # 7. After 03:30 PM: Market Closed
        if current_time >= dtime(15, 30) and not dry_run:
            print(f"[{now.strftime('%H:%M:%S')}] Market Closed for the day (03:30 PM). Monitor sleeping until tomorrow 09:00 AM.")
            time.sleep(3600)
            scan_completed_today = False
            continue
            
        if dry_run:
            print("Dry Run single pass completed.")
            break
            
        time.sleep(30) # Poll every 30 seconds

if __name__ == '__main__':
    is_dry = '--dry-run' in sys.argv
    monitor_live_session(dry_run=is_dry)
