import os
import json
from datetime import datetime
from angel_data_feed import get_angel_client, load_instrument_map

def scan_stg2(max_picks=2):
    smart = get_angel_client()
    imap = load_instrument_map()
    
    focus_symbols = [
        "RELIANCE", "TATASTEEL", "HDFCBANK", "ICICIBANK", "INFY",
        "SBIN", "KEI", "WOCKPHARMA", "CHENNPETRO", "GRAPHITE",
        "HEG", "DIXON", "POLYCAB", "TRENT", "HAL", "BEL",
        "COALINDIA", "VEDL", "VOLTAS", "TCS"
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
            
        ratio = buy_qty / sell_qty if sell_qty > 0 else (99.9 if buy_qty > 0 else 1.0)
        
        # LONG Candidate: Price > VWAP and Buyer Dominance
        if ltp > vwap and ltp >= open_p and ratio >= 1.5:
            sl = round(max(vwap, open_p * 0.99), 2)
            risk = round(abs(ltp - sl), 2)
            if risk > 0 and (risk / ltp) <= 0.025:
                t1 = round(ltp + 1.5 * risk, 2)
                t2 = round(ltp + 2.5 * risk, 2)
                score = round(ratio * 10 + ((ltp - vwap) / vwap) * 100, 1)
                candidates.append({
                    "symbol": sym, "direction": "LONG", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "buy_qty": buy_qty,
                    "sell_qty": sell_qty, "ratio": round(ratio, 2), "volume": volume, "score": score
                })
                
        # SHORT Candidate: Price < VWAP and Seller Dominance
        elif ltp < vwap and ltp <= open_p and ratio <= 0.67:
            sl = round(min(vwap, open_p * 1.01), 2)
            risk = round(abs(sl - ltp), 2)
            if risk > 0 and (risk / ltp) <= 0.025:
                t1 = round(ltp - 1.5 * risk, 2)
                t2 = round(ltp - 2.5 * risk, 2)
                score = round((1.0 / max(0.01, ratio)) * 10 + ((vwap - ltp) / vwap) * 100, 1)
                candidates.append({
                    "symbol": sym, "direction": "SHORT", "entry": ltp, "sl": sl,
                    "target1": t1, "target2": t2, "vwap": vwap, "buy_qty": buy_qty,
                    "sell_qty": sell_qty, "ratio": round(ratio, 2), "volume": volume, "score": score
                })
                
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:max_picks]

if __name__ == "__main__":
    print("Running STG2 Live Scan via AngelOne SmartAPI (Console test only)...")
    res = scan_stg2(max_picks=2)
    print(f"STG2 Identified {len(res)} Setups:")
    for r in res:
        print(r)
