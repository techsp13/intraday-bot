import urllib.request
import urllib.parse
import json
import time
import os
from datetime import datetime
import config
from chart_generator import generate_candlestick_chart

def send_telegram_message(message: str, parse_mode: str = 'Markdown') -> bool:
    """Send a text message to Telegram via Bot API (supports multiple comma-separated chat IDs)."""
    if not getattr(config, 'TELEGRAM_ALERTS_ENABLED', True):
        return False
        
    token = getattr(config, 'TELEGRAM_BOT_TOKEN', '')
    raw_chat_ids = getattr(config, 'TELEGRAM_CHAT_ID', '')
    
    if not token or not raw_chat_ids:
        return False
        
    chat_ids = [c.strip() for c in str(raw_chat_ids).split(',') if c.strip()]
    success_any = False
    
    for cid in chat_ids:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": cid,
            "text": message,
            "parse_mode": parse_mode
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    success_any = True
        except Exception:
            pass
            
    return success_any

def send_photo_alert(photo_path: str, caption: str, parse_mode: str = 'Markdown') -> bool:
    """Send a photo with caption to Telegram using pure urllib multipart/form-data."""
    if not getattr(config, 'TELEGRAM_ALERTS_ENABLED', True):
        return False
        
    token = getattr(config, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(config, 'TELEGRAM_CHAT_ID', '')
    
    if not token or not chat_id or not os.path.exists(photo_path):
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    
    with open(photo_path, 'rb') as f:
        photo_bytes = f.read()
        
    body = bytearray()
    
    # chat_id field
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
    body.extend(f'{chat_id}\r\n'.encode())
    
    # caption field
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
    body.extend(f'{caption}\r\n'.encode())
    
    # parse_mode field
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n')
    body.extend(f'{parse_mode}\r\n'.encode())
    
    # photo file field
    filename = os.path.basename(photo_path)
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'.encode())
    body.extend(b'Content-Type: image/png\r\n\r\n')
    body.extend(photo_bytes)
    body.extend(b'\r\n')
    body.extend(f'--{boundary}--\r\n'.encode())
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }
    
    req = urllib.request.Request(url, data=bytes(body), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                return True
    except Exception as e:
        print(f"Error sending photo alert: {e}")
        
    return False

def send_pick_alert(pick: dict) -> bool:
    """Format and send an alert for a single stock pick with candlestick chart image."""
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
    
    if alert_type == 'top2' or len(picks) <= 2:
        msg = f"🎯 *FINAL FILTERED TOP 2 PICKS — {date_str} (09:00 AM)*\n"
        msg += f"▸ *Pre-Market Confirmation for 09:15 AM Entry*\n"
    else:
        msg = f"📋 *NSE INTRADAY WATCHLIST — {date_str} (08:30 AM)*\n"
        msg += f"▸ *All {len(picks)} Qualifying Setups for Today*\n"
        
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for i, p in enumerate(picks, 1):
        sym = p.get('symbol', 'UNKNOWN')
        dirn = p.get('direction', 'LONG').upper()
        ent = float(p.get('entry', 0.0))
        sl = float(p.get('sl', 0.0))
        t1 = float(p.get('target1', 0.0))
        t2 = float(p.get('target2', 0.0))
        qty = p.get('position_size', 10)
        rs = float(p.get('adx', 0.0))
        
        badge = "🟢 LONG (BUY)" if dirn == 'LONG' else "🔴 SHORT (SELL)"
        sl_pct = "-2%" if dirn == 'LONG' else "+2%"
        t1_pct = "+3%" if dirn == 'LONG' else "-3%"
        t2_pct = "+5%" if dirn == 'LONG' else "-5%"
        
        msg += f"*{i}️⃣ {sym}* — {badge}\n"
        msg += f"▸ Entry: `₹{ent:,.2f}` | SL: `₹{sl:,.2f}` ({sl_pct})\n"
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
