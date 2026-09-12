import os
import json
from datetime import datetime
from angel_data_feed import get_angel_client, load_instrument_map

def scan_stg2(max_picks=2):
    smart = get_angel_client()
    imap = load_instrument_map()
    
    # Focus strictly on high-beta explosive momentum stocks (ATR >= 2.5%)
    # Mega-caps like HDFCBANK/INFY are banned to prevent small-capital brokerage bleed
    focus_symbols = [
        "GRAPHITE", "CHENNPETRO", "WOCKPHARMA", "KEI", "DIXON",
        "POLYCAB", "TRENT", "HAL", "BEL", "VEDL", "VOLTAS", "HEG"
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
        
        if ltp <= 0 or vwap <= 0 or open_p <= 0:
            continue
            
        # 15-Minute Range Expansion Filter: Minimum 1.8% range to qualify as explosive runner
        range_pct = ((high_p - low_p) / open_p) * 100.0
        if range_pct < 1.8:
            continue
            
        ratio = buy_qty / sell_qty if sell_qty > 0 else (99.9 if buy_qty > 0 else 1.0)
        
        # LONG Candidate: Price > VWAP, Buyer Dominance (>= 1.8x), and 15m Range Expansion
        if ltp > vwap and ltp >= open_p and ratio >= 1.8:
            sl = round(max(vwap, low_p), 2)
            risk = round(abs(ltp - sl), 2)
            if risk > 0 and (risk / ltp) <= 0.025:
                t1 = round(ltp + 1.5 * risk, 2)
                t2 = round(ltp + 2.5 * risk, 2)
                score = round(ratio * 10 + range_pct * 5 + ((ltp - vwap) / vwap) * 100, 1)
                candidates.append({
                    "symbol": sym, "direction": "LONG", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "range_pct": round(range_pct, 2),
                    "buy_qty": buy_qty, "sell_qty": sell_qty, "ratio": round(ratio, 2),
                    "volume": volume, "score": score
                })
                
        # SHORT Candidate: Price < VWAP, Seller Dominance (ratio <= 0.55), and 15m Range Expansion
        elif ltp < vwap and ltp <= open_p and ratio <= 0.55:
            sl = round(min(vwap, high_p), 2)
            risk = round(abs(sl - ltp), 2)
            if risk > 0 and (risk / ltp) <= 0.025:
                t1 = round(ltp - 1.5 * risk, 2)
                t2 = round(ltp - 2.5 * risk, 2)
                score = round((1.0 / max(0.01, ratio)) * 10 + range_pct * 5 + ((vwap - ltp) / vwap) * 100, 1)
                candidates.append({
                    "symbol": sym, "direction": "SHORT", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "range_pct": round(range_pct, 2),
                    "buy_qty": buy_qty, "sell_qty": sell_qty, "ratio": round(ratio, 2),
                    "volume": volume, "score": score
                })
                
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:max_picks]

if __name__ == "__main__":
    print("Running STG2 Live Scan via AngelOne SmartAPI (Console test only)...")
    res = scan_stg2(max_picks=2)
    print(f"STG2 Identified {len(res)} Setups:")
    for r in res:
        print(r)
