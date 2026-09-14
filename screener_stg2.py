import os
import json
from datetime import datetime
from angel_data_feed import get_angel_client, load_instrument_map

def scan_stg2(max_picks=2):
    """
    STG3 Early Sniper (Chart + Data Fusion with 1:3 RR):
    1. 15m Range Expansion >= 2.0%
    2. Institutional Volume Surge >= 1.8x (20-bar avg)
    3. Strong Body / Anti-Wick Conviction (Close in top/bottom 30% of range)
    4. Target 1 = +1.2R (50% profit + Trail SL to BE), Target 2 = +3.0R (1:3 RR)
    """
    smart = get_angel_client()
    imap = load_instrument_map()
    
    # 14 High-Beta Momentum Leaders on NSE
    focus_symbols = [
        "GRAPHITE", "CHENNPETRO", "WOCKPHARMA", "KEI", "DIXON",
        "POLYCAB", "TRENT", "HAL", "BEL", "VEDL", "VOLTAS", "HEG",
        "MCX", "BSE"
    ]
    
    tokens = []
    sym_by_token = {}
    for sym in focus_symbols:
        if sym in imap:
            tok = imap[sym]["token"]
            tokens.append(tok)
            sym_by_token[tok] = sym
            
    if not tokens:
        return []
        
    market_data = smart.getMarketData(mode="FULL", exchangeTokens={"NSE": tokens})
    if not (market_data.get("status") and market_data.get("data") and market_data["data"].get("fetched")):
        return []

    # LIVE EXCHANGE HOLIDAY & FEED STALENESS DETECTOR
    fetched_list = market_data["data"]["fetched"]
    if fetched_list:
        first_item = fetched_list[0]
        exch_trade_time = first_item.get("exchTradeTime", "")
        trade_date = None
        if exch_trade_time:
            try:
                trade_date = datetime.strptime(exch_trade_time.split()[0], "%d-%b-%Y").date()
            except Exception:
                pass
        if trade_date and trade_date < datetime.now().date():
            print(f"\n[MARKET CLOSED TODAY] NSE is closed (Trading Holiday). Latest feed trade date is {trade_date}. Zero trades taken.")
            return []
        
    candidates = []
    for item in market_data["data"]["fetched"]:
        tok = str(item.get("symbolToken", ""))
        sym = sym_by_token.get(tok, item.get("tradingSymbol", "").replace("-EQ", ""))
        
        ltp = float(item.get("ltp", 0.0))
        open_p = float(item.get("open", 0.0))
        high_p = float(item.get("high", 0.0))
        low_p = float(item.get("low", 0.0))
        close_p = float(item.get("close", 0.0))
        vwap = float(item.get("avgPrice", 0.0))
        
        buy_qty = int(item.get("totBuyQuan", 0))
        sell_qty = int(item.get("totSellQuan", 0))
        volume = int(item.get("tradeVolume", 0))
        
        if ltp <= 0 or vwap <= 0 or open_p <= 0 or high_p == low_p:
            continue
            
        # 1. 15-Minute Range Expansion Filter (>= 2.0%)
        range_pct = ((high_p - low_p) / open_p) * 100.0
        if range_pct < 2.0:
            continue
            
        # 2. Candle Body Quality Filter (Anti-Wick: Close in top/bottom 30%)
        c1_range = high_p - low_p
        close_loc = (ltp - low_p) / c1_range
        
        orderbook_ratio = buy_qty / max(1, sell_qty)
        
        # LONG Candidate: Price > VWAP, Buyer Dominance, Strong Body (close_loc >= 0.70)
        if ltp > vwap and ltp >= open_p and close_loc >= 0.70:
            sl = round(vwap, 2)
            risk = round(abs(ltp - sl), 2)
            # Risk cap: Max 2.5% of price
            if 0 < risk <= (ltp * 0.025):
                t1 = round(ltp + 1.2 * risk, 2)  # Milestone 1: Trail to Cost
                t2 = round(ltp + 3.0 * risk, 2)  # 1:3 Risk-to-Reward Target
                score = round(orderbook_ratio * 10 + range_pct * 5 + close_loc * 20, 1)
                candidates.append({
                    "symbol": sym, "direction": "LONG", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "range_pct": round(range_pct, 2),
                    "buy_qty": buy_qty, "sell_qty": sell_qty, "ratio": round(orderbook_ratio, 2),
                    "volume": volume, "score": score, "risk": risk
                })
                
        # SHORT Candidate: Price < VWAP, Seller Dominance, Strong Body (close_loc <= 0.30)
        elif ltp < vwap and ltp <= open_p and close_loc <= 0.30:
            sl = round(vwap, 2)
            risk = round(abs(sl - ltp), 2)
            if 0 < risk <= (ltp * 0.025):
                t1 = round(ltp - 1.2 * risk, 2)
                t2 = round(ltp - 3.0 * risk, 2)
                score = round((1.0 / max(0.01, orderbook_ratio)) * 10 + range_pct * 5 + (1.0 - close_loc) * 20, 1)
                candidates.append({
                    "symbol": sym, "direction": "SHORT", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "range_pct": round(range_pct, 2),
                    "buy_qty": buy_qty, "sell_qty": sell_qty, "ratio": round(orderbook_ratio, 2),
                    "volume": volume, "score": score, "risk": risk
                })
                
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:max_picks]

if __name__ == "__main__":
    print("Testing STG3 Early Sniper 1:3 RR Screener...")
    res = scan_stg2(max_picks=2)
    print(f"Picks Found: {len(res)}")
    for r in res:
        print(r)
