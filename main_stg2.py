"""
STG2 Live Pipeline Runner (09:30 AM Golden Window)
Powered exclusively by AngelOne SmartAPI.
"""
import sys
import os
import io
import time
from datetime import datetime

# Windows UTF-8 console fix
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
from screener_stg2 import scan_stg2
import alerts

def run_stg2_pipeline(dry_run: bool = False, test_personal_only: bool = False):
    print("=== STG2 Live Sniper Engine (09:30 AM Golden Window) ===")
    print(f"Time: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')} IST")
    print(f"Data Source: AngelOne SmartAPI (Live Level-2 Depth & VWAP)")
    print(f"Capital: ₹{getattr(config, 'CAPITAL_BASE', 5000):,.0f}\n")
    
    picks = scan_stg2(max_picks=2)
    print(f"STG2 Identified {len(picks)} High-Conviction Setups.")
    
    if not picks:
        print("No valid STG2 setups met the strict 15m ORB + VWAP + Buyer/Seller criteria today.")
        return
        
    date_str = datetime.now().strftime("%d-%b-%Y")
    msg = f"🎯 *STG2: 15-MIN ORB + VWAP SNIPER — {date_str} (09:30 AM)*\n"
    msg += f"▸ *Live Market Depth & Order Book Imbalance Confirmed*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for i, p in enumerate(picks, 1):
        sym = p["symbol"]
        dirn = p["direction"]
        badge = "🟢 LONG (BUY)" if dirn == "LONG" else "🔴 SHORT (SELL)"
        action = "Buy" if dirn == "LONG" else "Sell"
        entry = p["entry"]
        sl = p["sl"]
        t1 = p["target1"]
        t2 = p["target2"]
        vwap = p["vwap"]
        ratio = p["ratio"]
        buy_q = p["buy_qty"]
        sell_q = p["sell_qty"]
        
        # Position sizing for Rs. 5,000 capital (5x MIS margin)
        pos_val = 12500.0
        qty = max(1, int(pos_val / entry))
        risk_amt = round(abs(entry - sl) * qty, 0)
        
        msg += f"*{i}️⃣ {sym}* — {badge}\n"
        msg += f"▸ *Entry*: `₹{entry:,.2f}` ({action} at 09:30 AM breakout)\n"
        msg += f"▸ Stop Loss: `₹{sl:,.2f}` | VWAP: `₹{vwap:,.2f}`\n"
        msg += f"▸ Target 1: `₹{t1:,.2f}` (+1.5R) | Target 2: `₹{t2:,.2f}` (+2.5R)\n"
        msg += f"▸ Sized Qty: *{qty} shares* (Risk: ~₹{risk_amt})\n"
        if dirn == "LONG":
            msg += f"▸ Order Book: 🟢 *{buy_q:,} Buyers* vs {sell_q:,} Sellers ({ratio:.1f}x Demand)\n\n"
        else:
            msg += f"▸ Order Book: 🔴 *{sell_q:,} Sellers* vs {buy_q:,} Buyers (Heavy Supply)\n\n"
            
    msg += "━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "⏰ *Execution*: Valid between 09:30 AM – 10:15 AM only\n"
    msg += "🛡️ *Square-off*: 03:15 PM | *Discipline*: Strictly max 2 trades"
    
    print("\n--- FORMATTED STG2 ALERT ---")
    print(msg)
    print("----------------------------\n")
    
    if dry_run:
        print("Dry Run mode: Zero alerts sent.")
    elif test_personal_only:
        print("Sending test alert strictly to personal chat...")
        alerts.send_test_alert(msg)
        print("Personal-only alert sent.")
    else:
        print("Broadcasting STG2 morning alert...")
        alerts.send_telegram_message(msg)
        print("Alert broadcast complete.")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    is_test_personal = "--test-personal" in sys.argv
    run_stg2_pipeline(dry_run=is_dry, test_personal_only=is_test_personal)
