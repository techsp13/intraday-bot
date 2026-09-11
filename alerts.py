import urllib.request
import urllib.parse
import json
import time
import os
from datetime import datetime
import config

def send_telegram_message(message: str, parse_mode: str = 'Markdown', personal_only: bool = False) -> bool:
    """Send a text message to Telegram via Bot API. If personal_only=True, only sends to Sanket personal chat."""
    if not getattr(config, 'TELEGRAM_ALERTS_ENABLED', True):
        return False
        
    token = getattr(config, 'TELEGRAM_BOT_TOKEN', '')
    if personal_only:
        raw_chat_ids = getattr(config, 'PERSONAL_CHAT_ID', '8620674286')
    else:
        raw_chat_ids = getattr(config, 'TELEGRAM_CHAT_ID', '')
    
    if not token or not raw_chat_ids:
        return False
        
    chat_ids = [c.strip() for c in str(raw_chat_ids).split(',') if c.strip()]
    success_any = False
    
    # Split message into chunks if longer than Telegram's 4096 character limit
    chunks = []
    if len(message) <= 3900:
        chunks.append(message)
    else:
        current_chunk = ""
        for line in message.split("\n"):
            if len(current_chunk) + len(line) + 1 > 3900:
                chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk.strip():
            chunks.append(current_chunk)

    for cid in chat_ids:
        for chunk in chunks:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": cid,
                "text": chunk.strip(),
                "parse_mode": parse_mode
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        success_any = True
            except Exception as e:
                print(f"Telegram error sending to {cid}: {e}")
                
    return success_any

def send_test_alert(message: str, parse_mode: str = 'Markdown') -> bool:
    """Strictly send test and debug messages ONLY to personal chat ID, NEVER to group."""
    return send_telegram_message(message, parse_mode=parse_mode, personal_only=True)

def send_pick_alert(pick: dict) -> bool:
    """Format and send a clean text alert for a single stock pick."""
    direction = pick.get('direction', 'LONG').upper()
    symbol = pick.get('symbol', 'UNKNOWN')
    entry = pick.get('entry', 0.0)
    sl = pick.get('sl', 0.0)
    target1 = pick.get('target1', 0.0)
    target2 = pick.get('target2', 0.0)
    qty = pick.get('position_size', 0)
    risk_amt = pick.get('risk_amount', 0.0)
    adx = pick.get('adx', 0.0)
    vol_ratio = pick.get('volume_ratio', 0.0)
    score = pick.get('score', 0)
    breakout_time = pick.get('breakout_time', 'N/A')
    
    date_str = datetime.now().strftime("%d-%b-%Y")
    risk = abs(entry - sl)
    
    emoji = "🟢" if direction == 'LONG' else "🔴"
    header_emoji = "🚀" if direction == 'LONG' else "📉"
        
    msg = f"""{header_emoji} *INTRADAY PICK — {direction}*

📊 *{symbol}*
━━━━━━━━━━━━━━━━━━━━━━━
▸ Direction:   {emoji} {direction}
▸ Entry:       ₹{entry:.2f}
▸ Stop Loss:   ₹{sl:.2f}
▸ Risk (R):    ₹{risk:.2f}
━━━━━━━━━━━━━━━━━━━━━━━
🎯 Target 1:   ₹{target1:.2f}  (1.5R)
🎯 Target 2:   ₹{target2:.2f}  (2.5R)
📦 Qty:        {qty} shares
💰 Risk Amt:   ₹{risk_amt:.0f}
━━━━━━━━━━━━━━━━━━━━━━━
📈 RS Score: +{adx:.1f}% | Vol: {vol_ratio:.1f}x avg
📊 Score: {score}/100
⏰ Entry Window: {breakout_time}
📅 {date_str}"""

    return send_telegram_message(msg)

def send_picks_batch(picks: list[dict], alert_type: str = 'watchlist') -> int:
    """Send stock picks in ONE single consolidated Telegram alert."""
    if not picks:
        return 0
        
    date_str = datetime.now().strftime("%d-%b-%Y")
    
    msg = f"📋 *NSE INTRADAY PICKS — {date_str} (08:30 AM)*\n"
    msg += f"▸ *{len(picks)} Qualifying Setups for Today*\n"
        
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for i, p in enumerate(picks, 1):
        sym = p.get('symbol', 'UNKNOWN')
        dirn = p.get('direction', 'LONG').upper()
        ent = float(p.get('entry', 0.0))
        ent_min = float(p.get('entry_min', round(ent * 0.995, 2)))
        ent_max = float(p.get('entry_max', round(ent * 1.005, 2)))
        sl = float(p.get('sl', 0.0))
        t1 = float(p.get('target1', 0.0))
        t2 = float(p.get('target2', 0.0))
        qty = p.get('position_size', 10)
        rs = float(p.get('adx', 0.0))
        
        badge = "🟢 LONG (BUY)" if dirn == 'LONG' else "🔴 SHORT (SELL)"
        action_verb = "Buy" if dirn == 'LONG' else "Sell"
        sl_pct = "-2%" if dirn == 'LONG' else "+2%"
        t1_pct = "+3%" if dirn == 'LONG' else "-3%"
        t2_pct = "+5%" if dirn == 'LONG' else "-5%"
        
        msg += f"*{i}️⃣ {sym}* — {badge}\n"
        msg += f"▸ *Entry Zone*: `₹{ent_min:,.2f} – ₹{ent_max:,.2f}` ({action_verb} around open)\n"
        msg += f"▸ SL: `₹{sl:,.2f}` ({sl_pct}) | Ref: `₹{ent:,.2f}`\n"
        msg += f"▸ T1: `₹{t1:,.2f}` ({t1_pct}) | T2: `₹{t2:,.2f}` ({t2_pct})\n"
        msg += f"▸ Qty: *{qty} shares* | RS: *{rs:+.1f}%*\n\n"
        
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🌐 *Live Dashboard*: https://techsp13.github.io/intraday-bot/\n"
    msg += f"⏰ *Entry*: 09:15 AM Market Open | *Square-off*: 03:15 PM"
    
    if send_telegram_message(msg):
        return len(picks)
    return 0

def send_no_picks_alert() -> bool:
    """Send alert when no picks are found."""
    date_str = datetime.now().strftime("%d-%b-%Y")
    msg = f"📭 *No qualifying setups today*\nAll filters active. Market Regime / RS filters active.\n📅 {date_str}"
    return send_telegram_message(msg)

def send_daily_loss_halt_alert(cumulative_pnl: float) -> bool:
    """Send alert when daily loss limit is hit."""
    date_str = datetime.now().strftime("%d-%b-%Y")
    msg = f"⚠️ *DAILY LOSS LIMIT HIT*\nCumulative P&L: ₹{cumulative_pnl:.2f}\nHalting all new picks for today.\n📅 {date_str}"
    return send_telegram_message(msg)

def send_squareoff_reminder(active_picks: list[dict]) -> bool:
    """Send a reminder to square off open positions."""
    date_str = datetime.now().strftime("%d-%b-%Y")
    n = len(active_picks)
    msg = f"🔔 *SQUARE-OFF REMINDER — 3:15 PM*\n{n} picks were active today. Review and close positions.\n📅 {date_str}\n"
    
    for pick in active_picks:
        msg += f"\n▸ {pick.get('symbol', 'UNKNOWN')} ({pick.get('direction', 'LONG')})"
        
    return send_telegram_message(msg)

def send_daily_summary_alert(summary: dict) -> bool:
    """Send daily performance summary."""
    date_str = datetime.now().strftime("%d-%b-%Y")
    n = summary.get('total_picks', 0)
    triggered = summary.get('triggered', 0)
    t1 = summary.get('hit_t1', 0)
    t2 = summary.get('hit_t2', 0)
    sl = summary.get('hit_sl', 0)
    win_rate = summary.get('win_rate', 0.0)
    avg_r = summary.get('avg_r_multiple', 0.0)
    pnl = summary.get('daily_pnl', 0.0)
    
    msg = f"""📊 *DAILY PERFORMANCE REPORT*
━━━━━━━━━━━━━━━━━━━━━━━
📅 {date_str}
▸ Total Picks:    {n}
▸ Triggered:      {triggered}
▸ Hit T1:         {t1}
▸ Hit T2:         {t2}
▸ Hit SL:         {sl}
▸ Win Rate:       {win_rate:.1f}%
▸ Avg R Multiple: {avg_r:.2f}R
━━━━━━━━━━━━━━━━━━━━━━━
💵 Net P&L:  ₹{pnl:.2f}"""
    return send_telegram_message(msg)

def send_error_alert(error_msg: str) -> bool:
    """Send system error alert."""
    timestamp = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    msg = f"⚠️ *SYSTEM ERROR*\n{timestamp}\n`{error_msg}`"
    return send_telegram_message(msg)
