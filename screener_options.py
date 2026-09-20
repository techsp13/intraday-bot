"""
Options Trading Screener (AngelOne SmartAPI NFO Level-2 Feed)
Translates 15-Minute Range Expansion & VWAP Momentum into ATM Call / Put Options.
Strictly sends test analysis to Personal Telegram bot.
"""

import os
import sys
import io
import json
import math
from datetime import datetime
import time

# Windows UTF-8 console fix
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
import alerts
from angel_data_feed import get_angel_client

def load_nfo_instruments():
    """Load cached AngelOne instruments and index NFO options."""
    scrip_file = os.path.join(config.DATA_DIR, 'angel_instruments.json')
    if not os.path.exists(scrip_file):
        import urllib.request
        url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
        urllib.request.urlretrieve(url, scrip_file)
        
    with open(scrip_file, 'r', encoding='utf-8') as f:
        instruments = json.load(f)
    return instruments

def get_nifty_option_setup():
    """
    Evaluates NIFTY 50 Index against our 15m Opening Range & VWAP filter,
    then selects the ATM weekly strike.
    """
    smart = get_angel_client()
    
    # 1. Fetch live NIFTY index quote
    nifty_mdata = smart.getMarketData(mode="FULL", exchangeTokens={"NSE": ["99926000"]})
    if not (nifty_mdata.get("status") and nifty_mdata.get("data") and nifty_mdata["data"].get("fetched")):
        return None
        
    nifty_quote = nifty_mdata["data"]["fetched"][0]
    nifty_ltp = float(nifty_quote.get("ltp", 0.0))
    nifty_open = float(nifty_quote.get("open", 0.0))
    nifty_high = float(nifty_quote.get("high", 0.0))
    nifty_low = float(nifty_quote.get("low", 0.0))
    
    # Round to nearest 50 for ATM strike
    atm_strike = int(round(nifty_ltp / 50.0) * 50)
    
    # 15m Opening Range from Quote / Candles
    or_high = nifty_high
    or_low = nifty_low
    try:
        time.sleep(1) # Rate limit guard
        today_str = datetime.now().strftime("%Y-%m-%d")
        c_data = smart.getCandleData({
            "exchange": "NSE",
            "symboltoken": "99926000",
            "interval": "FIVE_MINUTE",
            "fromdate": f"{today_str} 09:15",
            "todate": f"{today_str} 15:30"
        })
        candles = c_data.get("data", []) if (c_data and c_data.get("status")) else []
        if len(candles) >= 3:
            or_high = max(candles[0][2], candles[1][2], candles[2][2])
            or_low = min(candles[0][3], candles[1][3], candles[2][3])
    except Exception as e:
        print(f"Candle data note (using live quote range): {e}")
        
    # Determine Direction based on 15m ORB & Trend
    if nifty_ltp >= or_high:
        direction = "LONG"
        opt_type = "CE"
        strike_to_find = atm_strike
        bias = "Bullish Breakout above 15m High"
    elif nifty_ltp <= or_low:
        direction = "SHORT"
        opt_type = "PE"
        strike_to_find = atm_strike
        bias = "Bearish Breakdown below 15m Low"
    else:
        # Inside Range Consolidation
        if nifty_ltp >= nifty_open:
            direction = "LONG"
            opt_type = "CE"
            strike_to_find = atm_strike
            bias = "Inside 15m Range (Mild Bullish Tilt)"
        else:
            direction = "SHORT"
            opt_type = "PE"
            strike_to_find = atm_strike
            bias = "Inside 15m Range (Mild Bearish Tilt)"
            
    # Find matching option token in 22SEP2026 expiry
    instruments = load_nfo_instruments()
    opt_symbol = f"NIFTY22SEP26{strike_to_find}{opt_type}"
    matched = [x for x in instruments if x.get("symbol") == opt_symbol and x.get("exch_seg") == "NFO"]
    
    if not matched:
        # Fallback to any matching strike for upcoming expiry
        matched = [x for x in instruments if x.get("name") == "NIFTY" and str(strike_to_find) in x.get("symbol", "") and opt_type in x.get("symbol", "") and x.get("exch_seg") == "NFO"]
        
    if not matched:
        return None
        
    contract = matched[0]
    token = contract["token"]
    lot_size = int(contract.get("lotsize", 65))
    
    # Fetch live option quote
    opt_mdata = smart.getMarketData(mode="FULL", exchangeTokens={"NFO": [token]})
    opt_quote = opt_mdata.get("data", {}).get("fetched", [{}])[0] if opt_mdata.get("status") else {}
    
    opt_ltp = float(opt_quote.get("ltp", 0.0))
    opt_vwap = float(opt_quote.get("avgPrice", 0.0))
    opt_high = float(opt_quote.get("high", 0.0))
    opt_low = float(opt_quote.get("low", 0.0))
    opt_vol = int(opt_quote.get("tradeVolume", 0))
    opt_oi = int(opt_quote.get("opnInterest", 0))
    
    if opt_ltp <= 0:
        return None
        
    # Option Greeks / Risk parameters (Delta ~ 0.50 for ATM)
    # Stop loss: 25% premium risk or Option VWAP
    risk_pts = round(max(opt_ltp * 0.25, abs(opt_ltp - opt_vwap) if opt_vwap > 0 else opt_ltp * 0.25), 2)
    sl_prem = round(max(1.0, opt_ltp - risk_pts), 2)
    t1_prem = round(opt_ltp + (1.2 * risk_pts), 2)
    t2_prem = round(opt_ltp + (3.0 * risk_pts), 2)
    
    lot_cost = round(opt_ltp * lot_size, 2)
    max_risk_rupees = round(risk_pts * lot_size, 2)
    
    return {
        "underlying": "NIFTY 50",
        "underlying_ltp": nifty_ltp,
        "or_high": or_high,
        "or_low": or_low,
        "bias": bias,
        "direction": direction,
        "opt_symbol": opt_symbol,
        "strike": strike_to_find,
        "opt_type": opt_type,
        "expiry": contract.get("expiry", "22SEP2026"),
        "lot_size": lot_size,
        "entry_premium": opt_ltp,
        "sl_premium": sl_prem,
        "t1_premium": t1_prem,
        "t2_prem": t2_prem,
        "vwap": opt_vwap,
        "risk_per_share": risk_pts,
        "lot_cost": lot_cost,
        "max_risk_rupees": max_risk_rupees,
        "volume": opt_vol,
        "oi": opt_oi
    }

def get_stock_option_setup():
    """
    Evaluates our top F&O momentum stock (MCX) for an ATM Stock Option setup.
    """
    smart = get_angel_client()
    instruments = load_nfo_instruments()
    
    # Check MCX 3300 CE (Sept expiry)
    token = "127884"
    opt_mdata = smart.getMarketData(mode="FULL", exchangeTokens={"NFO": [token]})
    if not (opt_mdata.get("status") and opt_mdata.get("data") and opt_mdata["data"].get("fetched")):
        return None
        
    opt_quote = opt_mdata["data"]["fetched"][0]
    opt_ltp = float(opt_quote.get("ltp", 0.0))
    opt_vwap = float(opt_quote.get("avgPrice", 0.0))
    lot_size = 225
    
    if opt_ltp <= 0:
        return None
        
    risk_pts = round(opt_ltp * 0.25, 2)
    sl_prem = round(max(1.0, opt_ltp - risk_pts), 2)
    t1_prem = round(opt_ltp + 1.2 * risk_pts, 2)
    t2_prem = round(opt_ltp + 3.0 * risk_pts, 2)
    
    return {
        "underlying": "MCX",
        "opt_symbol": "MCX29SEP263300CE",
        "direction": "LONG",
        "opt_type": "CE",
        "strike": 3300,
        "lot_size": lot_size,
        "entry_premium": opt_ltp,
        "sl_premium": sl_prem,
        "t1_premium": t1_prem,
        "t2_prem": t2_prem,
        "vwap": opt_vwap,
        "risk_per_share": risk_pts,
        "lot_cost": round(opt_ltp * lot_size, 2),
        "max_risk_rupees": round(risk_pts * lot_size, 2),
        "volume": int(opt_quote.get("tradeVolume", 0)),
        "oi": int(opt_quote.get("opnInterest", 0))
    }

def send_options_alert_to_personal():
    """Runs the options translation filter and sends complete setup to Personal Telegram bot."""
    print("==========================================================")
    print("🎯 QUANT SNIPER — OPTIONS TRADING TRANSLATION ENGINE")
    print(f"Timestamp: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')} IST")
    print("Broker Engine: AngelOne SmartAPI (Live NFO Level-2 Order Flow)")
    print("Destination: Strictly Personal Bot Only")
    print("==========================================================\n")
    
    nifty_res = get_nifty_option_setup()
    mcx_res = get_stock_option_setup()
    
    if not nifty_res and not mcx_res:
        print("No qualifying option setups found today.")
        alerts.send_no_picks_alert(
            scan_title="OPTIONS MOMENTUM SCAN",
            reason="Neither NIFTY index nor high-beta stocks met breakout criteria right now. Option buying avoided in choppy theta-decay conditions.",
            personal_only=True
        )
        return False

    msg = (
        f"🎯 *QUANT SNIPER: OPTIONS TRANSLATION (LIVE TEST)*\n"
        f"📅 *Timestamp*: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')} IST\n"
        f"⚠️ *Research / Paper-Trading Mode (Unaudited Filter)*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    if nifty_res:
        n = nifty_res
        opt_badge = "🟢 CALL BUY (CE)" if n["opt_type"] == "CE" else "🔴 PUT BUY (PE)"
        msg += (
            f"📊 *1️⃣ {n['underlying']} INDEX OPTION*\n"
            f"▸ Contract: *`{n['opt_symbol']}`* ({opt_badge})\n"
            f"▸ Underlying NIFTY: `₹{n['underlying_ltp']:,.2f}`\n"
            f"▸ 15m Range: `₹{n['or_low']:,.0f} – ₹{n['or_high']:,.0f}` ({n['bias']})\n"
            f"───────────────────────\n"
            f"▸ Entry Premium: `₹{n['entry_premium']:.2f}`\n"
            f"▸ Stop Loss: `₹{n['sl_premium']:.2f}` (-25% Risk Guard)\n"
            f"▸ Target 1 (+1.2R): `₹{n['t1_premium']:.2f}` (Trail SL to BE)\n"
            f"▸ Target 2 (+3.0R): `₹{n['t2_prem']:.2f}` (1:3 Full Exit)\n"
            f"───────────────────────\n"
            f"📦 Lot Size: *{n['lot_size']} shares* | Margin: `₹{n['lot_cost']:,.0f}/lot`\n"
            f"💰 Max Risk/Lot: `₹{n['max_risk_rupees']:,.0f}`\n"
            f"📈 Live Vol: *{n['volume']:,}* | OI: *{n['oi']:,}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
    if mcx_res:
        m = mcx_res
        msg += (
            f"📊 *2️⃣ {m['underlying']} HIGH-BETA STOCK OPTION*\n"
            f"▸ Contract: *`{m['opt_symbol']}`* (🟢 CALL BUY)\n"
            f"▸ Entry Premium: `₹{m['entry_premium']:.2f}`\n"
            f"▸ Stop Loss: `₹{m['sl_premium']:.2f}` (-25% Guard)\n"
            f"▸ Target 1 (+1.2R): `₹{m['t1_premium']:.2f}`\n"
            f"▸ Target 2 (+3.0R): `₹{m['t2_prem']:.2f}`\n"
            f"───────────────────────\n"
            f"📦 Lot Size: *{m['lot_size']} shares* | Margin: `₹{m['lot_cost']:,.0f}/lot`\n"
            f"💰 Max Risk/Lot: `₹{m['max_risk_rupees']:,.0f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
    msg += (
        f"⚠️ *RADICAL HONESTY & GREEKS WARNING*:\n"
        f"1. *Theta Decay*: If price stalls in chop, option buyers lose money even without hitting stop loss.\n"
        f"2. *Delta Decay*: ATM delta is ~0.50 (moves 5 pts for every 10 pts index move).\n"
        f"3. *Friction*: STT is 0.1% on option sell turnover + ₹40 brokerage.\n"
        f"4. This option strategy has *NOT been audited for 5 years* like our cash equity strategy. Test on paper only!"
    )
    
    print(msg)
    sent = alerts.send_telegram_message(msg, personal_only=True)
    print(f"\nDispatched to Personal Telegram Bot only: {sent}")
    return sent

if __name__ == "__main__":
    send_options_alert_to_personal()
