"""
Second-Half (01:15 PM IST) Experimental Intraday Screener
Purpose: Testing and Research Analysis Only.
Strictly adheres to AngelOne SmartAPI data and full transparency rules.
"""

import os
import sys
import json
import io
from datetime import datetime

# Windows UTF-8 console fix
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
import alerts
import nse_holidays
from angel_data_feed import get_angel_client, load_instrument_map

FOCUS_SYMBOLS = [
    "GRAPHITE", "CHENNPETRO", "WOCKPHARMA", "KEI", "DIXON",
    "POLYCAB", "TRENT", "HAL", "BEL", "VEDL", "VOLTAS", "HEG",
    "MCX", "BSE"
]

def scan_second_half(max_picks=2):
    """
    Second-Half Momentum Breakout Filter:
    1. Executed during European Open window (01:15 - 01:45 PM IST).
    2. Long: LTP > VWAP, breaking or within 0.5% of Day High, Buyer dominance > 1.2x.
    3. Short: LTP < VWAP, breaking or within 0.5% of Day Low, Seller dominance > 1.2x.
    4. Targets adjusted for 03:15 PM MIS Square-Off:
       - T1: +1.0R (Book 50% & Trail SL to Entry)
       - T2: +2.0R (Realistic 1:2 R:R given ~90 min holding window)
    """
    print("==========================================================")
    print("🧪 SECOND-HALF (01:15 PM) TEST SCREENER — LIVE ANALYSIS")
    print(f"Timestamp: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')} IST")
    print("Engine: AngelOne SmartAPI (Live L2 Order Flow)")
    print("Mode: EXPERIMENTAL / RESEARCH ANALYSIS ONLY")
    print("==========================================================\n")

    # Holiday Check
    is_closed, holiday_reason = nse_holidays.is_market_holiday()
    if is_closed:
        print(f"[MARKET CLOSED] {holiday_reason}")
        return []

    smart = get_angel_client()
    imap = load_instrument_map()

    tokens = []
    sym_by_token = {}
    for sym in FOCUS_SYMBOLS:
        if sym in imap:
            tok = imap[sym]["token"]
            tokens.append(tok)
            sym_by_token[tok] = sym

    if not tokens:
        print("Error: No valid instrument tokens found.")
        return []

    market_data = smart.getMarketData(mode="FULL", exchangeTokens={"NSE": tokens})
    if not (market_data.get("status") and market_data.get("data") and market_data["data"].get("fetched")):
        print("Failed to fetch full market depth from AngelOne.")
        return []

    fetched = market_data["data"]["fetched"]
    candidates = []

    for item in fetched:
        tok = str(item.get("symbolToken", ""))
        sym = sym_by_token.get(tok, item.get("tradingSymbol", "").replace("-EQ", ""))

        ltp = float(item.get("ltp", 0.0))
        open_p = float(item.get("open", 0.0))
        high_p = float(item.get("high", 0.0))
        low_p = float(item.get("low", 0.0))
        vwap = float(item.get("avgPrice", 0.0))

        buy_qty = int(item.get("totBuyQuan", 0))
        sell_qty = int(item.get("totSellQuan", 0))
        volume = int(item.get("tradeVolume", 0))

        if ltp <= 0 or vwap <= 0 or high_p == low_p:
            continue

        day_range_pct = ((high_p - low_p) / open_p) * 100.0
        orderbook_ratio = buy_qty / max(1, sell_qty)

        # Afternoon Long: Above VWAP + within 0.5% of Day High (or new High) + Buyer Dominance >= 1.2
        if ltp > vwap and ltp >= (high_p * 0.995) and orderbook_ratio >= 1.2:
            sl = round(vwap, 2)
            risk = round(abs(ltp - sl), 2)
            max_risk = ltp * 0.02 # Capped at 2.0%
            if 0 < risk <= max_risk:
                t1 = round(ltp + 1.0 * risk, 2)
                t2 = round(ltp + 2.0 * risk, 2)
                score = round(orderbook_ratio * 10 + day_range_pct * 3, 1)
                candidates.append({
                    "symbol": sym, "direction": "LONG", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "day_range_pct": round(day_range_pct, 2),
                    "buy_qty": buy_qty, "sell_qty": sell_qty, "ratio": round(orderbook_ratio, 2),
                    "volume": volume, "score": score, "risk": risk, "day_high": high_p, "day_low": low_p
                })

        # Afternoon Short: Below VWAP + within 0.5% of Day Low (or new Low) + Seller Dominance >= 1.2
        elif ltp < vwap and ltp <= (low_p * 1.005) and (1.0 / max(0.01, orderbook_ratio)) >= 1.2:
            sl = round(vwap, 2)
            risk = round(abs(sl - ltp), 2)
            max_risk = ltp * 0.02 # Capped at 2.0%
            if 0 < risk <= max_risk:
                t1 = round(ltp - 1.0 * risk, 2)
                t2 = round(ltp - 2.0 * risk, 2)
                seller_ratio = round(sell_qty / max(1, buy_qty), 2)
                score = round(seller_ratio * 10 + day_range_pct * 3, 1)
                candidates.append({
                    "symbol": sym, "direction": "SHORT", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "day_range_pct": round(day_range_pct, 2),
                    "buy_qty": buy_qty, "sell_qty": sell_qty, "ratio": seller_ratio,
                    "volume": volume, "score": score, "risk": risk, "day_high": high_p, "day_low": low_p
                })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = candidates[:max_picks]

    # Save to data directory for records
    picks_file = os.path.join(config.DATA_DIR, "second_half_test_picks.json")
    with open(picks_file, "w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2)

    return selected

def send_afternoon_analysis_alert(picks, personal_only: bool = True):
    """Formats and dispatches the second-half analysis to Telegram (Personal by default for testing)."""
    date_str = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
    
    if not picks:
        msg = (
            f"🧪 *SECOND-HALF SCAN ANALYSIS (01:15 PM IST)*\n\n"
            f"📅 *Time*: {date_str}\n"
            f"▸ *Result*: *0 Qualifying Breakouts*\n"
            f"▸ *Market State*: Midday consolidation continues. No stocks broke Day High/Low with institutional buyer/seller volume dominance.\n"
            f"▸ *Risk Rule*: Capital 100% protected in cash. No forced midday entries."
        )
        alerts.send_telegram_message(msg, personal_only=personal_only)
        print(f"\nAlert dispatched to Telegram (Personal only: {personal_only}): No afternoon candidates.")
        return

    msg = (
        f"🧪 *[TESTING / ANALYSIS ONLY] SECOND-HALF SCAN (01:15 PM)*\n"
        f"⚠️ *Research / Paper-Trading Mode (Unaudited Filter)*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    for i, p in enumerate(picks, 1):
        sym = p["symbol"]
        dirn = p["direction"]
        badge = "🟢 LONG (BUY)" if dirn == "LONG" else "🔴 SHORT (SELL)"
        ratio_label = "Buyer Ratio" if dirn == "LONG" else "Seller Ratio"
        
        msg += (
            f"*{i}️⃣ {sym}* — {badge}\n"
            f"▸ Trigger: `₹{p['entry']:,.2f}`\n"
            f"▸ Stop Loss: `₹{p['sl']:,.2f}` (VWAP Anchor)\n"
            f"▸ Target 1 (+1.0R): `₹{p['target1']:,.2f}` (Trail to BE)\n"
            f"▸ Target 2 (+2.0R): `₹{p['target2']:,.2f}` (Square-off by 03:15)\n"
            f"▸ Intraday VWAP: `₹{p['vwap']:,.2f}`\n"
            f"▸ {ratio_label}: *{p['ratio']}x*\n"
            f"▸ Day Range: *{p['day_range_pct']}%*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
    msg += "⚠️ *Auto-Square-Off Note*: All MIS positions must be exited by 03:15 PM."
    
    # Try sending chart if possible
    import chart_data_fusion
    for p in picks:
        sym = p["symbol"]
        try:
            fusion_res = chart_data_fusion.analyze_chart_and_data(sym, save_chart=True)
            chart_path = fusion_res.get("chart_path", "")
            if chart_path and not os.path.isabs(chart_path):
                chart_path = os.path.join(config.BASE_DIR, chart_path)
            if chart_path and os.path.exists(chart_path):
                alerts.send_telegram_photo(chart_path, caption=msg, personal_only=personal_only)
                print(f"Dispatched Telegram photo alert for {sym} (Personal only: {personal_only})")
                return
        except Exception as e:
            print(f"Chart generation error: {e}")

    alerts.send_telegram_message(msg, personal_only=personal_only)
    print(f"\nDispatched Telegram text alert (Personal only: {personal_only}).")

if __name__ == "__main__":
    picks = scan_second_half(max_picks=2)
    print(f"\nFound {len(picks)} second-half candidates:")
    for p in picks:
        print(f"- {p['symbol']} ({p['direction']}) Entry: {p['entry']} | SL: {p['sl']} | T1: {p['target1']} | T2: {p['target2']}")
    
    # Send test analysis to Telegram
    send_afternoon_analysis_alert(picks)
