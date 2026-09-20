"""
YouTube Live Stream Real-Time Price Simulation Engine
Simulates discrete tick-by-tick institutional price flow,
updates stream_hud_state.json, and triggers synchronized buy/sell alerts.
"""

import os
import sys
import io
import time
import json
from datetime import datetime

# Windows UTF-8 console fix
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
import alerts

HUD_STATE_FILE = os.path.join(config.DATA_DIR, "stream_hud_state.json")
ACTIVE_TRADES_FILE = os.path.join(config.DATA_DIR, "active_stg2_trades.json")

# Discrete institutional sequence
TICK_SEQUENCE = [
    {"ltp": 4820.00, "step": "09:30 AM ENTRY TRIGGER", "log": "🟢 BUY SIGNAL: HAL Breakout @ ₹4,820.00. SL: ₹4,785.00 | T1: ₹4,862.00 | T2: ₹4,925.00", "t1": False, "t2": False, "sl_trailed": False},
    {"ltp": 4827.50, "step": "MOMENTUM EXPANSION", "log": "Institutional volume surge detected: 72% buyers dominating order book.", "t1": False, "t2": False, "sl_trailed": False},
    {"ltp": 4836.00, "step": "5M CANDLE 1 CLOSE", "log": "First 5-minute candle closed bullish (+₹16.00). Trailing VWAP rising.", "t1": False, "t2": False, "sl_trailed": False},
    {"ltp": 4845.00, "step": "APPROACHING TARGET 1", "log": "Breakout velocity accelerating: HAL @ ₹4,845.00. Buyer ratio: 2.3x.", "t1": False, "t2": False, "sl_trailed": False},
    {"ltp": 4854.00, "step": "TESTING RESISTANCE", "log": "Buyers absorbing supply above ₹4,850.00. Target 1 within reach.", "t1": False, "t2": False, "sl_trailed": False},
    {"ltp": 4862.50, "step": "🎯 TARGET 1 HIT (+1.2R)", "log": "🎯 TARGET 1 HIT (+1.2R) @ ₹4,862.00! 50% profit secured. SL trailed to Cost (₹4,820.00). 100% RISK FREE!", "t1": True, "t2": False, "sl_trailed": True},
    {"ltp": 4878.00, "step": "RUNNER MANAGEMENT", "log": "Holding above Target 1 with ₹0 downside risk. Letting 50% runner aim for 1:3 payout.", "t1": True, "t2": False, "sl_trailed": True},
    {"ltp": 4895.00, "step": "INSTITUTIONAL WAVE 2", "log": "Volume expanding +2.8x. HAL breaking into fresh day highs @ ₹4,895.00.", "t1": True, "t2": False, "sl_trailed": True},
    {"ltp": 4912.00, "step": "APPROACHING 1:3 RR", "log": "HAL @ ₹4,912.00. Just 13 points away from full 1:3 target exit.", "t1": True, "t2": False, "sl_trailed": True},
    {"ltp": 4925.00, "step": "🎉 1:3 TARGET 2 HIT (+3.0R)", "log": "🎉 1:3 RR TARGET 2 HIT (+3.0R) @ ₹4,925.00! Full position squared off. +₹3 profit on ₹1 risk! 💰", "t1": True, "t2": True, "sl_trailed": True}
]

def run_simulation(send_telegram: bool = True):
    print("========================================================================")
    print("🚀 QUANT SNIPER — YOUTUBE STREAM REAL-TIME PRICE SIMULATOR")
    print("Live Dashboard: youtube_stream_hud.html (TradingView 16:9 OBS HUD)")
    print("Feed: Discrete Tick-by-Tick Institutional Replay")
    print(f"Telegram Alerts: {'ENABLED (Personal Chat)' if send_telegram else 'DISABLED'}")
    print("========================================================================\n")

    if send_telegram:
        alerts.send_telegram_message(
            "🎬 *YOUTUBE LIVE STREAM SIMULATION STARTED*\n\n"
            "▸ Instrument: *HAL* (LONG)\n"
            "▸ Breakout Entry: `₹4,820.00`\n"
            "▸ Initial Stop Loss: `₹4,785.00` (VWAP)\n"
            "▸ Target 1 (+1.2R): `₹4,862.00` (Lock 50% & Trail SL)\n"
            "▸ Target 2 (+3.0R): `₹4,925.00` (Full 1:3 Exit)\n\n"
            "Watch your live stream HUD update in real-time!",
            personal_only=True
        )

    for idx, item in enumerate(TICK_SEQUENCE, 1):
        cur_price = item["ltp"]
        entry = 4820.00
        target1 = 4862.00
        target2 = 4925.00
        sl = 4820.00 if item["sl_trailed"] else 4785.00
        
        diff = cur_price - entry
        pct = (diff / entry) * 100
        
        # Calculate real-world net PnL after ₹45 taxes on 10 shares
        gross_pnl = diff * 10
        net_pnl = round(gross_pnl - 45.0, 2) if gross_pnl > 0 else round(gross_pnl - 25.0, 2)
        
        # Build HUD state object
        state_data = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "active_trade": {
                "symbol": "HAL",
                "direction": "LONG",
                "entry": entry,
                "sl": sl,
                "target1": target1,
                "target2": target2,
                "ltp": cur_price,
                "t1_hit": item["t1"],
                "t2_hit": item["t2"],
                "sl_hit": False,
                "entry_time": "09:30:00",
                "net_pnl": net_pnl
            },
            "all_trades": [
                {
                    "symbol": "HAL", "direction": "LONG", "entry": entry, "sl": sl,
                    "target1": target1, "target2": target2, "t1_hit": item["t1"], "t2_hit": item["t2"]
                }
            ],
            "log": item["log"]
        }
        
        # Save to stream_hud_state.json
        with open(HUD_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
            
        with open(ACTIVE_TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump([state_data["active_trade"]], f, indent=2)
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Step {idx}/{len(TICK_SEQUENCE)}: {item['step']}")
        print(f"   LTP: ₹{cur_price:,.2f} ({diff:+.2f} pts) | Net P&L: ₹{net_pnl:+,.2f}")
        print(f"   Log: {item['log']}\n")
        
        # Dispatch milestone Telegram alerts
        if send_telegram:
            if item["step"] == "🎯 TARGET 1 HIT (+1.2R)":
                alerts.send_telegram_message(
                    "🎯 *TARGET 1 HIT (+1.2R) on HAL!* @ `₹4,862.00`\n\n"
                    "▸ *Action*: 50% Profit Booked! 💰\n"
                    "▸ *Trailing SL*: Moved to Entry (Cost: `₹4,820.00`).\n"
                    "▸ *Downside Risk*: **₹0.00 (100% Risk-Free)**\n"
                    "▸ *Runner Goal*: Aiming for 1:3 Target 2 (`₹4,925.00`)",
                    personal_only=True
                )
            elif item["step"] == "🎉 1:3 TARGET 2 HIT (+3.0R)":
                alerts.send_telegram_message(
                    "🎉 *1:3 RR TARGET 2 HIT (+3.0R) on HAL!* @ `₹4,925.00`\n\n"
                    "▸ *Action*: Complete Position Exited! 🏆\n"
                    "▸ *Payout*: ₹3 Profit Realized on ₹1 Risk!\n"
                    "▸ *Session Status*: 100% Target Met. Day Complete.",
                    personal_only=True
                )
                
        time.sleep(3)

    print("========================================================================")
    print("✅ SIMULATION COMPLETE: Full 1:3 RR Breakout Lifecycle Replayed!")
    print("========================================================================")

if __name__ == "__main__":
    send_tg = "--telegram" in sys.argv
    run_simulation(send_telegram=send_tg)
