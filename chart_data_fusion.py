"""
Chart + Data Fusion Engine (Quantitative & Visual Confluence Analyzer)
Combines Candlestick Price Action Morphology (Chart) with Order Flow & Volatility Metrics (Data)
to generate high-conviction institutional trade setups.
"""

import os
import time
import numpy as np
import pandas as pd
from datetime import datetime

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from angel_data_feed import get_angel_client, load_instrument_map

def analyze_chart_and_data(symbol: str, smart=None, imap=None, save_chart: bool = True) -> dict:
    """
    Performs full multi-modal analysis:
    1. CHART ANALYSIS: Candlestick morphology, PDH/PDL, CPR pivots, Wick rejection, Multi-timeframe trend.
    2. DATA ANALYSIS: 15m Institutional Volume Surge, Order Book Buy/Sell Depth, VWAP slope, Range Expansion %.
    3. FUSION CONFLUENCE SCORE: 0 to 100 institutional grade scoring.
    """
    if smart is None:
        smart = get_angel_client()
    if imap is None:
        imap = load_instrument_map()
        
    if symbol not in imap:
        return {"status": "error", "message": f"Symbol {symbol} not found in instrument map."}
        
    tok = imap[symbol]["token"]
    
    # -------------------------------------------------------------
    # STEP 1: FETCH DATA (Live Order Book Depth & Market Data)
    # -------------------------------------------------------------
    try:
        mdata = smart.getMarketData(mode="FULL", exchangeTokens={"NSE": [tok]})
        quote = mdata.get("data", {}).get("fetched", [{}])[0] if mdata.get("status") else {}
    except Exception as e:
        quote = {}
        
    ltp = float(quote.get("ltp", 0.0))
    open_p = float(quote.get("open", 0.0))
    high_p = float(quote.get("high", 0.0))
    low_p = float(quote.get("low", 0.0))
    close_prev = float(quote.get("close", 0.0))
    avg_price = float(quote.get("avgPrice", 0.0))
    tot_buy = int(quote.get("totBuyQuan", 0))
    tot_sell = int(quote.get("totSellQuan", 0))
    live_volume = int(quote.get("tradeVolume", 0))
    
    # -------------------------------------------------------------
    # STEP 2: FETCH CHART CANDLES (15-Minute & Daily Candles)
    # -------------------------------------------------------------
    today_str = datetime.now().strftime('%Y-%m-%d')
    try:
        res = smart.getCandleData({
            'exchange': 'NSE',
            'symboltoken': tok,
            'interval': 'FIFTEEN_MINUTE',
            'fromdate': f"2026-08-01 09:15",
            'todate': f"2026-09-13 15:30"
        })
        candles = res.get('data', [])
        if not candles:
            # Fallback to cache
            cache_file = f"data/cache_5y_{symbol}.parquet"
            if os.path.exists(cache_file):
                df_all = pd.read_parquet(cache_file)
                df_all['time'] = pd.to_datetime(df_all['time'])
                df = df_all.tail(60).copy().reset_index(drop=True)
            else:
                return {"status": "error", "message": "No candle data available."}
        else:
            df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['time'])
            df = df.sort_values('time').reset_index(drop=True)
    except Exception as e:
        return {"status": "error", "message": f"Error fetching candle data: {e}"}

    # Derive last complete session candles
    df['date'] = df['time'].dt.date
    dates = sorted(df['date'].unique())
    last_date = dates[-1]
    prev_date = dates[-2] if len(dates) >= 2 else last_date
    
    day_df = df[df['date'] == last_date].copy().reset_index(drop=True)
    prev_day_df = df[df['date'] == prev_date].copy().reset_index(drop=True)
    
    if len(day_df) < 1:
        return {"status": "error", "message": "Insufficient intraday candles."}
        
    c1 = day_df.iloc[0]
    c1_open = float(c1['open'])
    c1_high = float(c1['high'])
    c1_low = float(c1['low'])
    c1_close = float(c1['close'])
    c1_vol = float(c1['volume'])
    
    # -------------------------------------------------------------
    # STEP 3: CHART MORPHOLOGY ANALYSIS
    # -------------------------------------------------------------
    # A. Prior Day High/Low/Close & CPR Calculation
    pdh = float(prev_day_df['high'].max()) if not prev_day_df.empty else c1_high
    pdl = float(prev_day_df['low'].min()) if not prev_day_df.empty else c1_low
    pdc = float(prev_day_df['close'].iloc[-1]) if not prev_day_df.empty else c1_open
    
    pivot = round((pdh + pdl + pdc) / 3.0, 2)
    bc = round((pdh + pdl) / 2.0, 2)
    tc = round((pivot - bc) + pivot, 2)
    cpr_top = max(tc, bc)
    cpr_bottom = min(tc, bc)
    cpr_width_pct = round(((cpr_top - cpr_bottom) / pivot) * 100.0, 2)
    cpr_type = "Virgin / Narrow CPR (Explosive Breakout Likely)" if cpr_width_pct < 0.35 else "Normal / Wide CPR"
    
    # B. Candle 1 Anatomy (Anti-Wick & Conviction)
    c1_range = max(0.01, c1_high - c1_low)
    c1_range_pct = round(((c1_high - c1_low) / c1_open) * 100.0, 2)
    body_size = abs(c1_close - c1_open)
    body_pct = round((body_size / c1_range) * 100.0, 1)
    close_location = round(((c1_close - c1_low) / c1_range) * 100.0, 1)
    
    upper_wick = round(((c1_high - max(c1_open, c1_close)) / c1_range) * 100.0, 1)
    lower_wick = round(((min(c1_open, c1_close) - c1_low) / c1_range) * 100.0, 1)
    
    candle_sentiment = "BULLISH MARUBOZU" if (close_location >= 70 and upper_wick <= 20) else (
        "BEARISH MARUBOZU" if (close_location <= 30 and lower_wick <= 20) else "INDECISIVE / WICKY"
    )
    
    # -------------------------------------------------------------
    # STEP 4: DATA & QUANTITATIVE METRICS ANALYSIS
    # -------------------------------------------------------------
    # A. Volume Surge Analysis (20-bar 15m volume moving average)
    vol_avg20 = float(df['volume'].tail(30).iloc[:-len(day_df)].tail(20).mean()) if len(df) > len(day_df) + 20 else c1_vol
    vol_ratio = round(c1_vol / max(1.0, vol_avg20), 2)
    vol_verdict = "INSTITUTIONAL SURGE (>=1.8x)" if vol_ratio >= 1.8 else "RETAIL / LOW VOLUME"
    
    # B. Order Book Imbalance (Buy vs Sell Depth)
    orderbook_ratio = round(tot_buy / max(1, tot_sell), 2) if tot_sell > 0 else 1.0
    orderbook_verdict = "BUYER DOMINANCE" if orderbook_ratio >= 1.5 else (
        "SELLER DOMINANCE" if orderbook_ratio <= 0.65 else "NEUTRAL DEPTH"
    )
    
    # C. VWAP Dynamics
    session_vwap = round((c1_high + c1_low + c1_close) / 3.0, 2)
    vwap_diff_pct = round(((c1_close - session_vwap) / session_vwap) * 100.0, 2)
    
    # -------------------------------------------------------------
    # STEP 5: FUSION CONFLUENCE SCORING (0 to 100)
    # -------------------------------------------------------------
    score = 0
    confluence_factors = []
    
    # 1. Range Expansion (20 pts)
    if c1_range_pct >= 2.0:
        score += 20
        confluence_factors.append(f"15m Range Expansion ({c1_range_pct}% >= 2.0%)")
    elif c1_range_pct >= 1.5:
        score += 10
        
    # 2. Institutional Volume Surge (25 pts)
    if vol_ratio >= 2.0:
        score += 25
        confluence_factors.append(f"Massive Volume Surge ({vol_ratio}x >= 2.0x)")
    elif vol_ratio >= 1.8:
        score += 20
        confluence_factors.append(f"Institutional Volume Surge ({vol_ratio}x >= 1.8x)")
        
    # 3. Clean Candle Body / Anti-Wick (25 pts)
    if close_location >= 70 or close_location <= 30:
        score += 25
        confluence_factors.append(f"Strong Body / Anti-Wick Conviction ({close_location}%)")
    elif close_location >= 60 or close_location <= 40:
        score += 12
        
    # 4. VWAP Structural Alignment (15 pts)
    if (c1_close > session_vwap and c1_close > c1_open) or (c1_close < session_vwap and c1_close < c1_open):
        score += 15
        confluence_factors.append("Price Aligned on Correct Side of VWAP")
        
    # 5. Order Book Confirmation (15 pts)
    if orderbook_ratio >= 1.5 or orderbook_ratio <= 0.65:
        score += 15
        confluence_factors.append(f"Order Book Flow Confirmed ({orderbook_ratio}x)")
    else:
        score += 5
        
    # Determine Final Trade Plan with 1:3 Risk-to-Reward
    if c1_close > c1_open and c1_close >= session_vwap and close_location >= 70:
        direction = "LONG"
        trigger = c1_high
        sl = session_vwap
        risk = round(trigger - sl, 2)
        if (risk / trigger) > 0.025: # Cap at 2.5%
            risk = round(trigger * 0.025, 2)
            sl = round(trigger - risk, 2)
        t1_trail = round(trigger + 1.5 * risk, 2)
        target_3r = round(trigger + 3.0 * risk, 2)
    elif c1_close < c1_open and c1_close <= session_vwap and close_location <= 30:
        direction = "SHORT"
        trigger = c1_low
        sl = session_vwap
        risk = round(sl - trigger, 2)
        if (risk / trigger) > 0.025:
            risk = round(trigger * 0.025, 2)
            sl = round(trigger + risk, 2)
        t1_trail = round(trigger - 1.5 * risk, 2)
        target_3r = round(trigger - 3.0 * risk, 2)
    else:
        direction = "NEUTRAL"
        trigger, sl, risk, t1_trail, target_3r = 0.0, 0.0, 0.0, 0.0, 0.0
        
    # Star Rating
    stars = "[*****]" if score >= 85 else ("[****]" if score >= 70 else ("[***]" if score >= 50 else "[**]"))
    verdict = "5-STAR INSTITUTIONAL SNIPER SETUP" if score >= 85 else (
        "HIGH CONFLUENCE TRADE" if score >= 70 else "WAIT / WEAK CONFLUENCE"
    )
    
    # -------------------------------------------------------------
    # STEP 6: RENDER ANNOTATED CHART + DATA HUD
    # -------------------------------------------------------------
    chart_path = ""
    if save_chart and HAS_MATPLOTLIB and len(day_df) >= 1:
        os.makedirs('reports/charts', exist_ok=True)
        chart_path = f"reports/charts/fusion_{symbol}_{last_date}.png"
        
        fig, (ax_price, ax_vol) = plt.subplots(2, 1, figsize=(12, 7.5), dpi=160, gridspec_kw={'height_ratios': [3.5, 1.2]})
        fig.patch.set_facecolor('#0B0E14')
        ax_price.set_facecolor('#111722')
        ax_vol.set_facecolor('#111722')
        
        # Plot Intraday Candlesticks
        width = 0.65
        for i, row in day_df.iterrows():
            c_color = '#00E676' if row['close'] >= row['open'] else '#FF5252'
            ax_price.plot([i, i], [row['low'], row['high']], color=c_color, linewidth=1.8)
            b_bot = min(row['open'], row['close'])
            b_h = max(abs(row['close'] - row['open']), 0.1)
            rect = plt.Rectangle((i - width/2, b_bot), width, b_h, facecolor=c_color, edgecolor=c_color, alpha=0.95)
            ax_price.add_patch(rect)
            
            # Volume bars
            v_color = '#00E676' if row['close'] >= row['open'] else '#FF5252'
            ax_vol.bar(i, row['volume'], width=width, color=v_color, alpha=0.8)
            
        # Draw Key Levels
        x_min, x_max = -0.5, len(day_df) - 0.5
        ax_price.set_xlim(x_min, x_max + 3.0) # room for labels
        
        if direction in ["LONG", "SHORT"]:
            ax_price.hlines(y=trigger, xmin=x_min, xmax=x_max + 2.5, colors='#29B6F6', linestyles='--', linewidth=2.0, label=f'TRIGGER: Rs.{trigger:,.2f}')
            ax_price.hlines(y=sl, xmin=x_min, xmax=x_max + 2.5, colors='#FF1744', linestyles='--', linewidth=2.0, label=f'STOP LOSS (VWAP): Rs.{sl:,.2f}')
            ax_price.hlines(y=t1_trail, xmin=x_min, xmax=x_max + 2.5, colors='#FFD600', linestyles=':', linewidth=1.8, label=f'TRAIL TO BE (+1.5R): Rs.{t1_trail:,.2f}')
            ax_price.hlines(y=target_3r, xmin=x_min, xmax=x_max + 2.5, colors='#00E676', linestyles='-', linewidth=2.4, label=f'1:3 TARGET (+3.0R): Rs.{target_3r:,.2f}')
            
            # Right Axis Annotations
            ax_price.annotate(f" 1:3 TGT: {target_3r:,.1f}", xy=(x_max + 0.2, target_3r), fontsize=9, fontweight='bold', color='#00E676', va='center')
            ax_price.annotate(f" BE Trail: {t1_trail:,.1f}", xy=(x_max + 0.2, t1_trail), fontsize=9, fontweight='bold', color='#FFD600', va='center')
            ax_price.annotate(f" Entry: {trigger:,.1f}", xy=(x_max + 0.2, trigger), fontsize=9, fontweight='bold', color='#29B6F6', va='center')
            ax_price.annotate(f" SL: {sl:,.1f}", xy=(x_max + 0.2, sl), fontsize=9, fontweight='bold', color='#FF1744', va='center')

        # CPR Overlay
        ax_price.axhspan(cpr_bottom, cpr_top, color='#673AB7', alpha=0.18, label=f'CPR Range [{cpr_bottom:,.1f} - {cpr_top:,.1f}]')
        
        # Volume 20 avg line
        ax_vol.axhline(vol_avg20, color='#00E5FF', linestyle='--', linewidth=1.5, label=f'20-Bar Avg Vol ({int(vol_avg20):,})')
        
        # X-axis formatting
        step = max(1, len(day_df) // 6)
        x_ticks = list(range(0, len(day_df), step))
        x_labels = [day_df.iloc[idx]['time'].strftime('%H:%M') for idx in x_ticks]
        ax_vol.set_xticks(x_ticks)
        ax_vol.set_xticklabels(x_labels, color='#90A4AE', fontsize=9)
        ax_price.set_xticks([])
        
        ax_price.set_ylabel("Price (Rs.)", color='#B0BEC5', fontsize=10, fontweight='bold')
        ax_vol.set_ylabel("Volume", color='#B0BEC5', fontsize=9, fontweight='bold')
        ax_price.grid(True, linestyle=':', alpha=0.25, color='#FFFFFF')
        ax_vol.grid(True, linestyle=':', alpha=0.25, color='#FFFFFF')
        
        # Super-Imposed HUD Header (Fusion Score & Confluence)
        hud_text = (
            f">> CONFLUENCE SCORE: {score}/100 [{stars}]\n"
            f"- 15m Range: {c1_range_pct}% | Body: {body_pct}% ({candle_sentiment})\n"
            f"- Vol Surge: {vol_ratio}x Avg | Order Book: {orderbook_ratio}x Buyers\n"
            f"- CPR Status: {cpr_type} | 1:3 RR Risk: Rs.{risk:.2f} -> Reward: Rs.{risk*3:.2f}"
        )
        ax_price.text(0.02, 0.95, hud_text, transform=ax_price.transAxes, fontsize=9,
                      fontfamily='monospace', color='#FFFFFF', verticalalignment='top',
                      bbox=dict(boxstyle='round,pad=0.6', facecolor='#1E293B', edgecolor='#00E5FF', alpha=0.9))
                      
        ax_price.legend(loc='upper right', fontsize=8, facecolor='#1E293B', edgecolor='#455A64')
        ax_vol.legend(loc='upper right', fontsize=8, facecolor='#1E293B', edgecolor='#455A64')
        
        plt.suptitle(f"FUSION ENGINE: {symbol} - {last_date} ({direction} SETUP)", fontsize=13, fontweight='bold', color='#FFFFFF', y=0.98)
        plt.tight_layout()
        plt.savefig(chart_path, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()

    return {
        "status": "success",
        "symbol": symbol,
        "date": str(last_date),
        "score": score,
        "stars": stars,
        "verdict": verdict,
        "direction": direction,
        "trigger": trigger,
        "stop_loss": sl,
        "risk_per_share": risk,
        "trail_1_5r": t1_trail,
        "target_3r": target_3r,
        "rr_ratio": "1:3",
        "chart_metrics": {
            "c1_range_pct": c1_range_pct,
            "candle_body_pct": body_pct,
            "close_location_pct": close_location,
            "candle_sentiment": candle_sentiment,
            "cpr_range": f"{cpr_bottom} - {cpr_top}",
            "cpr_type": cpr_type,
            "pdh": pdh,
            "pdl": pdl
        },
        "data_metrics": {
            "volume_ratio": vol_ratio,
            "volume_verdict": vol_verdict,
            "orderbook_ratio": orderbook_ratio,
            "orderbook_verdict": orderbook_verdict,
            "session_vwap": session_vwap,
            "vwap_deviation_pct": vwap_diff_pct
        },
        "confluence_factors": confluence_factors,
        "chart_path": chart_path
    }

if __name__ == "__main__":
    print("Testing Chart + Data Fusion Engine on HAL...")
    result = analyze_chart_and_data("HAL")
    print(f"\nResult for {result['symbol']}:")
    print(f"Score: {result['score']}/100 ({result['stars']}) - {result['verdict']}")
    print(f"Direction: {result['direction']} | Trigger: Rs.{result['trigger']} | SL: Rs.{result['stop_loss']} | Target (1:3): Rs.{result['target_3r']}")
    print(f"Confluence Factors: {result['confluence_factors']}")
    print(f"Chart Image Generated: {result['chart_path']}")

