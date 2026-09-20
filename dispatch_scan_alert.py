import os
import sys
import io

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
import alerts
import chart_data_fusion
from screener_stg2 import scan_stg2

print("Running Live Momentum Scan from AngelOne...")
picks = scan_stg2(max_picks=2)

if not picks:
    print("No qualifying picks found. Dispatching 0-stock protection alert to Telegram...")
    alerts.send_no_picks_alert(
        scan_title="MOMENTUM SNIPER SCAN",
        reason="None of the 14 high-beta momentum leaders met our strict 2.0% range expansion + VWAP conviction.",
        personal_only=True
    )
    sys.exit(0)

print(f"Found {len(picks)} setups. Dispatching alerts...")

for p in picks:
    sym = p["symbol"]
    dirn = p["direction"]
    badge = "🟢 LONG (BUY)" if dirn == "LONG" else "🔴 SHORT (SELL)"
    head_emoji = "🚀" if dirn == "LONG" else "📉"
    
    caption = (
        f"{head_emoji} *QUANT SNIPER LIVE ALERT (10:48 AM)*\n\n"
        f"*{sym}* — {badge}\n"
        f"⭐ Score: *{p.get('score', 75)}/100*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"▸ Entry Trigger: `₹{p['entry']:,.2f}`\n"
        f"▸ Stop Loss: `₹{p['sl']:,.2f}` (VWAP Anchor)\n"
        f"▸ Target 1 (+1.2R): `₹{p['target1']:,.2f}` (Trail SL to Cost)\n"
        f"▸ Target 2 (+3.0R): `₹{p['target2']:,.2f}` (1:3 RR Full Exit)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Order Book: *{p['buy_qty']:,} Buyers* vs *{p['sell_qty']:,} Sellers*\n"
        f"📈 15m Range Expansion: *{p['range_pct']}%*\n"
        f"⏰ Exit Window: Square-off by 03:15 PM."
    )
    
    # Try generating and sending HD chart
    chart_sent = False
    try:
        fusion_res = chart_data_fusion.analyze_chart_and_data(sym, save_chart=True)
        chart_path = fusion_res.get("chart_path", "")
        if chart_path and not os.path.isabs(chart_path):
            chart_path = os.path.join(config.BASE_DIR, chart_path)
        if chart_path and os.path.exists(chart_path):
            alerts.send_telegram_photo(chart_path, caption=caption, personal_only=True)
            print(f"Dispatched Photo Alert for {sym} to Personal Bot Only!")
            chart_sent = True
    except Exception as e:
        print(f"Chart generation note for {sym}: {e}")
        
    if not chart_sent:
        alerts.send_telegram_message(caption, personal_only=True)
        print(f"Dispatched Text Alert for {sym} to Personal Bot Only!")

print("All alerts dispatched successfully.")
