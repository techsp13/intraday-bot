"""
Clean, Simple & Mobile-Optimized Web Dashboard Generator for NSE Intraday Stock Pick Bot.
- Always loads the latest active trading date and stock picks.
- Interactive Demat Portfolio Capital Allocator (Enter ₹6,800 -> Auto-splits across stocks with 5x MIS leverage).
- Supports both LONG (Buy) and SHORT (Sell) trades with Entry Zones.
- Developed by Sanket Patel.
- Market Close Results & P&L.
"""
import os
import json
import sqlite3
from datetime import datetime
import yfinance as yf
import pandas as pd

def generate_site():
    """Generates a 100% mobile-friendly docs/index.html for GitHub Pages."""
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
    os.makedirs(docs_dir, exist_ok=True)
    
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'picks.db')
    json_path = os.path.join(docs_dir, 'picks.json')
    
    today_picks = []

    # 1. Try reading from docs/picks.json first (most accurate)
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                json_data = json.load(f)
                if json_data and isinstance(json_data, list):
                    today_picks = json_data
        except Exception as e:
            print(f"Error reading picks.json: {e}")

    # 2. If empty, fallback to picks.db
    if not today_picks and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM picks ORDER BY date DESC, id DESC")
            rows = c.fetchall()
            picks = [dict(r) for r in rows]
            conn.close()
            
            if picks:
                latest_date = picks[0].get('date')
                today_picks = [p for p in picks if p.get('date') == latest_date]
        except Exception as e:
            print(f"Error reading database: {e}")

    # Deduplicate symbols
    seen_symbols = set()
    deduped_today_picks = []
    for p in reversed(today_picks):
        sym = p.get('symbol')
        if sym and sym not in seen_symbols:
            seen_symbols.add(sym)
            deduped_today_picks.append(p)
    today_picks = list(reversed(deduped_today_picks))[:5]

    now = datetime.now()
    is_market_closed = (now.hour > 15) or (now.hour == 15 and now.minute >= 30)
    
    evaluated_picks = []
    total_day_pnl = 0.0

    for p in today_picks:
        symbol = p.get('symbol', 'STOCK')
        ticker = p.get('ticker', f"{symbol}.NS")
        direction = p.get('direction', 'LONG').upper()
        entry = float(p.get('entry', 0.0))
        
        if direction == 'LONG':
            sl = float(p.get('sl', round(entry * 0.98, 2)))
            t1 = float(p.get('target1', round(entry * 1.03, 2)))
            t2 = float(p.get('target2', round(entry * 1.05, 2)))
        else: # SHORT
            sl = float(p.get('sl', round(entry * 1.02, 2)))
            t1 = float(p.get('target1', round(entry * 0.97, 2)))
            t2 = float(p.get('target2', round(entry * 0.95, 2)))
            
        qty = int(p.get('position_size', 10))
        
        day_high, day_low, day_close = entry, entry, entry
        outcome = "ACTIVE"
        exit_price = entry

        if is_market_closed:
            try:
                df = yf.download(ticker, period="5d", interval="5m", progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
                
                today_df = df[df.index.date == df.index.date[-1]]
                if not today_df.empty:
                    day_high = round(float(today_df['High'].max()), 2)
                    day_low = round(float(today_df['Low'].min()), 2)
                    day_close = round(float(today_df.iloc[-1]['Close']), 2)
                    
                    if direction == 'LONG':
                        if day_high >= t2:
                            outcome = "HIT TARGET 2 (+5%)"
                            exit_price = t2
                        elif day_high >= t1:
                            outcome = "HIT TARGET 1 (+3%)"
                            exit_price = t1
                        elif day_low <= sl:
                            outcome = "HIT STOP LOSS (-2%)"
                            exit_price = sl
                        else:
                            outcome = "CLOSED AT 03:15 PM"
                            exit_price = day_close
                        pnl = round((exit_price - entry) * qty, 2)
                    else: # SHORT
                        if day_low <= t2:
                            outcome = "HIT TARGET 2 (+5%)"
                            exit_price = t2
                        elif day_low <= t1:
                            outcome = "HIT TARGET 1 (+3%)"
                            exit_price = t1
                        elif day_high >= sl:
                            outcome = "HIT STOP LOSS (-2%)"
                            exit_price = sl
                        else:
                            outcome = "CLOSED AT 03:15 PM"
                            exit_price = day_close
                        pnl = round((entry - exit_price) * qty, 2)
            except Exception:
                pnl = 0.0

            total_day_pnl += pnl
        else:
            pnl = 0.0

        evaluated_picks.append({
            'symbol': symbol,
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'target1': t1,
            'target2': t2,
            'qty': qty,
            'rs': float(p.get('rs', p.get('adx', 0.0))),
            'day_high': day_high,
            'day_low': day_low,
            'day_close': day_close,
            'exit_price': exit_price,
            'outcome': outcome,
            'pnl': pnl
        })

    with open(os.path.join(docs_dir, 'picks.json'), 'w') as f:
        json.dump(evaluated_picks, f, indent=2)

    today_date_display = datetime.now().strftime("%d-%b-%Y")
    total_pnl_sign = "+" if total_day_pnl >= 0 else ""
    total_pnl_color = "text-emerald-400" if total_day_pnl >= 0 else "text-rose-400"

    picks_js_data = json.dumps([{
        'symbol': p['symbol'],
        'direction': p['direction'],
        'entry': p['entry'],
        'sl': p['sl'],
        't1': p['target1'],
        't2': p['target2']
    } for p in evaluated_picks])

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>NSE Intraday Terminal | Developed by Sanket Patel</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700;800&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    body {{
      background-color: #0d1117;
      color: #e6edf3;
      font-family: 'Inter', sans-serif;
      -webkit-tap-highlight-color: transparent;
    }}
    .mono {{
      font-family: 'JetBrains Mono', monospace;
    }}
    .card {{
      background-color: #161b22;
      border: 1px solid #30363d;
    }}
    .card:hover {{
      border-color: #58a6ff;
    }}
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased">

  <!-- Header -->
  <header class="border-b border-[#30363d] bg-[#161b22]/95 sticky top-0 z-50 px-3 py-2.5 sm:px-4 sm:py-3">
    <div class="max-w-6xl mx-auto flex items-center justify-between">
      <div class="flex items-center space-x-2.5">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center font-bold text-gray-950 shadow">
          <i data-lucide="trending-up" class="w-4 h-4 sm:w-5 sm:h-5"></i>
        </div>
        <div>
          <div class="flex items-center gap-1.5">
            <h1 class="text-sm sm:text-base font-bold text-white leading-tight">NSE Intraday Terminal</h1>
            <span class="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20">{today_date_display}</span>
          </div>
          <p class="text-[11px] text-cyan-400 font-medium">
            Developed by <strong class="text-white">Sanket Patel</strong>
          </p>
        </div>
      </div>
      
      <a href="https://t.me/sany_trader_bot" target="_blank" class="px-2.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center gap-1 shadow transition-colors">
        <i data-lucide="send" class="w-3.5 h-3.5"></i> <span class="hidden xs:inline">Telegram Group</span>
      </a>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-6xl mx-auto w-full px-3 py-4 sm:px-4 sm:py-6 space-y-5">

    <!-- Section 1: Morning Stock Picks -->
    <div class="card rounded-xl p-4 sm:p-5 shadow-lg">
      <div class="flex items-center justify-between border-b border-[#30363d] pb-3 mb-4">
        <div>
          <h2 class="text-base sm:text-lg font-bold text-white flex items-center gap-2">
            <i data-lucide="zap" class="w-4 h-4 sm:w-5 sm:h-5 text-amber-400"></i>
            Today's 08:30 AM Stock Picks
          </h2>
          <p class="text-[11px] sm:text-xs text-gray-400">Buy/Sell at 09:15 AM Market Open | Set Stop Loss & Targets</p>
        </div>
        <span class="text-[11px] px-2 py-0.5 rounded bg-[#0d1117] text-gray-300 border border-[#30363d] mono">
          {len(evaluated_picks)} Stocks
        </span>
      </div>

      <!-- MOBILE VIEW: Stacked Clean Cards -->
      <div class="block md:hidden space-y-3">
"""

    for p in evaluated_picks:
        sym = p['symbol']
        dirn = p['direction']
        ent = p['entry']
        sl = p['sl']
        t1 = p['target1']
        t2 = p['target2']
        qty = p['qty']

        dirn_badge = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" if dirn == 'LONG' else "bg-rose-500/10 text-rose-400 border-rose-500/20"
        sl_label = "SL (-2%)" if dirn == 'LONG' else "SL (+2%)"
        t1_label = "T1 (+3%)" if dirn == 'LONG' else "T1 (-3%)"
        t2_label = "T2 (+5%)" if dirn == 'LONG' else "T2 (-5%)"

        html_content += f"""
        <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-3.5 space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <h3 class="text-lg font-bold text-white font-sans">{sym}</h3>
              <span class="text-[10px] px-2 py-0.5 rounded {dirn_badge} font-bold border">{dirn}</span>
            </div>
            <button onclick="calculateSingleStock('{sym}', '{ent}', '{dirn}')" class="px-3 py-1 rounded bg-[#21262d] hover:bg-cyan-600 text-cyan-400 hover:text-white text-xs font-semibold flex items-center gap-1 transition-colors">
              <i data-lucide="calculator" class="w-3 h-3"></i> Size Stock
            </button>
          </div>

          <div class="grid grid-cols-2 gap-2 bg-[#161b22] p-2.5 rounded-lg mono text-xs">
            <div>
              <span class="text-[10px] text-gray-400 block font-sans">Entry Ref</span>
              <span class="text-white font-bold text-sm">₹{ent:,.2f}</span>
            </div>
            <div>
              <span class="text-[10px] text-rose-400 block font-sans">{sl_label}</span>
              <span class="text-rose-400 font-bold text-sm">₹{sl:,.2f}</span>
            </div>
            <div>
              <span class="text-[10px] text-emerald-400 block font-sans">{t1_label}</span>
              <span class="text-emerald-400 font-bold text-sm">₹{t1:,.2f}</span>
            </div>
            <div>
              <span class="text-[10px] text-cyan-400 block font-sans">{t2_label}</span>
              <span class="text-cyan-400 font-bold text-sm">₹{t2:,.2f}</span>
            </div>
          </div>
          
          <div class="flex items-center justify-between text-[11px] text-gray-400 mono pt-1 border-t border-[#30363d]/60">
            <span>Entry Zone: <strong class="text-white">₹{round(ent*0.995, 2):,.2f} – ₹{round(ent*1.005, 2):,.2f}</strong></span>
          </div>
        </div>
"""

    html_content += f"""
      </div>

      <!-- DESKTOP VIEW: Full Wide Table -->
      <div class="hidden md:block overflow-x-auto">
        <table class="w-full text-left text-xs mono">
          <thead class="bg-[#0d1117] text-gray-400 uppercase text-[11px] border-b border-[#30363d]">
            <tr>
              <th class="px-4 py-3 font-sans">Stock</th>
              <th class="px-4 py-3">Direction</th>
              <th class="px-4 py-3 text-white">Entry Zone (±0.5%)</th>
              <th class="px-4 py-3 text-rose-400">Stop Loss (2%)</th>
              <th class="px-4 py-3 text-emerald-400">Target 1 (3%)</th>
              <th class="px-4 py-3 text-cyan-400">Target 2 (5%)</th>
              <th class="px-4 py-3 text-right">Calculator</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#30363d] text-gray-200">
"""

    for p in evaluated_picks:
        sym = p['symbol']
        dirn = p['direction']
        ent = p['entry']
        sl = p['sl']
        t1 = p['target1']
        t2 = p['target2']

        dirn_color = "text-emerald-400" if dirn == 'LONG' else "text-rose-400"

        html_content += f"""
            <tr class="hover:bg-[#1f242c] transition-colors">
              <td class="px-4 py-3.5 font-bold text-white text-sm font-sans">{sym}</td>
              <td class="px-4 py-3.5 {dirn_color} font-bold">{dirn}</td>
              <td class="px-4 py-3.5 font-bold text-white">₹{round(ent*0.995, 2):,.2f} – ₹{round(ent*1.005, 2):,.2f}</td>
              <td class="px-4 py-3.5 text-rose-400 font-semibold">₹{sl:,.2f}</td>
              <td class="px-4 py-3.5 text-emerald-400 font-semibold">₹{t1:,.2f}</td>
              <td class="px-4 py-3.5 text-cyan-400 font-semibold">₹{t2:,.2f}</td>
              <td class="px-4 py-3.5 text-right">
                <button onclick="calculateSingleStock('{sym}', '{ent}', '{dirn}')" class="px-2.5 py-1 rounded bg-[#21262d] hover:bg-cyan-600 text-gray-300 hover:text-white text-[11px] font-sans font-semibold transition-colors">
                  Size Stock
                </button>
              </td>
            </tr>
"""

    html_content += f"""
          </tbody>
        </table>
      </div>
    </div>

    <!-- Section 2: SMART PORTFOLIO CAPITAL ALLOCATOR & 5x MIS SIZER -->
    <div id="calculatorSection" class="card rounded-xl p-4 sm:p-5 border-cyan-500/50 shadow-xl space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[#30363d] pb-3 gap-2">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <i data-lucide="pie-chart" class="w-4 h-4 sm:w-5 sm:h-5"></i>
          </div>
          <div>
            <h3 class="text-sm sm:text-base font-bold text-white">Demat Capital Allocator & 5x MIS Calculator</h3>
            <p class="text-[11px] sm:text-xs text-gray-400">Enter your Total Demat Balance to auto-calculate exact shares for all stocks</p>
          </div>
        </div>

        <!-- Strategy Mode Selector -->
        <div class="flex items-center bg-[#0d1117] p-1 rounded-lg border border-[#30363d] text-xs font-bold mono self-start sm:self-auto">
          <button id="btnAll5" onclick="setPortfolioMode(5)" class="px-3 py-1 rounded bg-cyan-500 text-gray-950 font-bold transition-all">ALL 5 STOCKS</button>
          <button id="btnTop2" onclick="setPortfolioMode(2)" class="px-3 py-1 rounded text-gray-400 hover:text-white transition-all">TOP 2 ONLY</button>
        </div>
      </div>

      <!-- Input Controls -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        <div>
          <label class="block text-xs text-cyan-400 mb-1 font-bold">Your Total Demat Cash Balance (₹)</label>
          <div class="relative">
            <input type="number" id="inputDematCash" step="100" value="6800" oninput="recalculatePortfolio()" class="w-full bg-[#0d1117] border border-cyan-500/60 focus:border-cyan-400 rounded-lg p-2.5 pl-7 text-cyan-300 mono font-bold text-base outline-none">
            <span class="absolute left-2.5 top-2.5 text-gray-500 font-bold text-sm">₹</span>
          </div>
        </div>

        <div>
          <label class="block text-xs text-gray-400 mb-1 font-semibold">Cash Margin per Stock</label>
          <div id="dispMarginPerStock" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-2.5 text-white mono font-bold text-base">
            ₹1,360 / stock
          </div>
        </div>

        <div>
          <label class="block text-xs text-emerald-400 mb-1 font-semibold">Total Buying Power (5x MIS Leverage)</label>
          <div id="dispTotalBuyingPower" class="w-full bg-[#0d1117] border border-emerald-500/40 rounded-lg p-2.5 text-emerald-400 mono font-bold text-base">
            ₹34,000 (5x MIS)
          </div>
        </div>
      </div>

      <!-- Quick Presets -->
      <div class="flex flex-wrap items-center gap-2 text-xs font-mono">
        <span class="text-gray-500 font-sans text-[11px]">Quick Presets:</span>
        <button onclick="setQuickPreset(6800)" class="px-2.5 py-1 rounded bg-[#0d1117] hover:bg-[#21262d] text-cyan-300 border border-[#30363d]">₹6,800</button>
        <button onclick="setQuickPreset(10000)" class="px-2.5 py-1 rounded bg-[#0d1117] hover:bg-[#21262d] text-gray-300 border border-[#30363d]">₹10,000</button>
        <button onclick="setQuickPreset(20000)" class="px-2.5 py-1 rounded bg-[#0d1117] hover:bg-[#21262d] text-gray-300 border border-[#30363d]">₹20,000</button>
        <button onclick="setQuickPreset(50000)" class="px-2.5 py-1 rounded bg-[#0d1117] hover:bg-[#21262d] text-gray-300 border border-[#30363d]">₹50,000</button>
        <button onclick="setQuickPreset(100000)" class="px-2.5 py-1 rounded bg-[#0d1117] hover:bg-[#21262d] text-emerald-400 border border-emerald-500/30 font-bold">₹1,00,000 (1 Lakh)</button>
      </div>

      <!-- Dynamic Stock Allocation Cards -->
      <div class="space-y-2 pt-2 border-t border-[#30363d]">
        <h4 class="text-xs font-bold text-gray-300 uppercase font-mono tracking-wider flex items-center gap-1.5">
          <i data-lucide="layers" class="w-3.5 h-3.5 text-cyan-400"></i>
          Exact Position Sizing & Shares for Today's Stocks:
        </h4>
        
        <div id="portfolioAllocationContainer" class="space-y-2">
          <!-- Rendered by JS -->
        </div>
      </div>
    </div>

    <!-- Section 3: Trading Rules & Stock Selection Guide -->
    <div class="card rounded-xl p-4 sm:p-5 shadow-lg border-emerald-500/30">
      <div class="flex items-center gap-2 border-b border-[#30363d] pb-3 mb-4">
        <i data-lucide="book-open" class="w-5 h-5 text-emerald-400"></i>
        <div>
          <h3 class="text-sm sm:text-base font-bold text-white">How to Trade & Select the Best Stocks</h3>
          <p class="text-[11px] sm:text-xs text-gray-400">Simple rules to trade Long & Short setups safely</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        
        <!-- Long & Short Selection Rules -->
        <div class="space-y-2.5 bg-[#0d1117] p-3.5 rounded-xl border border-[#30363d]">
          <h4 class="font-bold text-cyan-400 text-xs sm:text-sm flex items-center gap-1.5">
            <i data-lucide="check-circle" class="w-4 h-4 text-cyan-400"></i>
            Stock Selection Strategy:
          </h4>
          
          <div class="space-y-2 text-gray-300 text-[11px] sm:text-xs">
            <div class="flex items-start gap-2">
              <span class="font-bold text-emerald-400 shrink-0">🟢</span>
              <p><strong class="text-white">For LONG Trades:</strong> Pick stocks opening <span class="text-emerald-400 font-semibold">GREEN</span> at 09:15 AM. Buy at open, set SL at -2.0% below entry.</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-rose-400 shrink-0">🔴</span>
              <p><strong class="text-white">For SHORT Trades:</strong> Pick stocks opening <span class="text-rose-400 font-semibold">RED</span> at 09:15 AM. Sell at open, set SL at +2.0% above entry.</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-amber-400 shrink-0">⚡</span>
              <p><strong class="text-white">Avoid Big Gaps (> ±1.5%):</strong> Skip any stock with huge opening gap to avoid opening reversals.</p>
            </div>
          </div>
        </div>

        <!-- Execution & Risk Management Rules -->
        <div class="space-y-2.5 bg-[#0d1117] p-3.5 rounded-xl border border-[#30363d]">
          <h4 class="font-bold text-emerald-400 text-xs sm:text-sm flex items-center gap-1.5">
            <i data-lucide="shield-check" class="w-4 h-4 text-emerald-400"></i>
            Execution & Risk Rules:
          </h4>
          
          <div class="space-y-2 text-gray-300 text-[11px] sm:text-xs">
            <div class="flex items-start gap-2">
              <span class="font-bold text-emerald-400 shrink-0">A.</span>
              <p><strong class="text-white">09:15 AM Entry:</strong> Place MIS orders at open. Calculate quantity using the calculator above.</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-rose-400 shrink-0">B.</span>
              <p><strong class="text-white">Strict 2.0% Stop Loss:</strong> Always place your SL order immediately. Never hold below/above 2%.</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-purple-400 shrink-0">C.</span>
              <p><strong class="text-white">03:15 PM Square-off:</strong> Exit all open positions before 03:20 PM (100% intraday MIS).</p>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- Section 4: Market Close Results (Reveals at 03:30 PM) -->
    <div class="card rounded-xl p-4 sm:p-5">
      <div class="flex items-center justify-between border-b border-[#30363d] pb-3 mb-4">
        <div>
          <h3 class="text-sm sm:text-base font-bold text-white flex items-center gap-2">
            <i data-lucide="check-circle-2" class="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400"></i>
            Market Close Results & P&L ({today_date_display})
          </h3>
          <p class="text-[11px] sm:text-xs text-gray-400">Official intraday closing results updated daily at 03:30 PM IST</p>
        </div>
"""

    if is_market_closed:
        html_content += f"""
        <div class="text-right">
          <span class="text-[10px] sm:text-xs text-gray-400 block">Total Net P&L</span>
          <span class="text-base sm:text-xl font-bold {total_pnl_color} mono">{total_pnl_sign}₹{total_day_pnl:,.2f}</span>
        </div>
      </div>

      <!-- Mobile Result Cards -->
      <div class="block md:hidden space-y-2.5">
"""
        for p in evaluated_picks:
            sym = p['symbol']
            dirn = p['direction']
            qty = p['qty']
            ent = p['entry']
            high = p['day_high']
            low = p['day_low']
            exit_p = p['exit_price']
            out = p['outcome']
            pnl = p['pnl']
            
            pnl_color = "text-emerald-400 font-bold" if pnl >= 0 else "text-rose-400 font-bold"
            pnl_sign = "+" if pnl >= 0 else ""
            badge = "text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-semibold text-[10px]" if "TARGET" in out else ("text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded font-semibold text-[10px]" if "LOSS" in out else "text-gray-300 bg-gray-800 px-2 py-0.5 rounded text-[10px]")
            dirn_color = "text-emerald-400" if dirn == 'LONG' else "text-rose-400"

            html_content += f"""
        <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-3 space-y-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              <h4 class="font-bold text-white text-base font-sans">{sym}</h4>
              <span class="text-[10px] font-mono font-bold {dirn_color}">({dirn})</span>
            </div>
            <span class="{badge}">{out}</span>
          </div>
          <div class="grid grid-cols-3 gap-2 bg-[#161b22] p-2 rounded-lg mono text-[11px] text-center">
            <div>
              <span class="text-[9px] text-gray-400 block font-sans">Entry</span>
              <span class="text-white font-semibold">₹{ent:,.2f}</span>
            </div>
            <div>
              <span class="text-[9px] text-amber-300 block font-sans">Exit</span>
              <span class="text-amber-300 font-bold">₹{exit_p:,.2f}</span>
            </div>
            <div>
              <span class="text-[9px] text-gray-400 block font-sans">Net P&L</span>
              <span class="{pnl_color} text-xs">{pnl_sign}₹{pnl:,.2f}</span>
            </div>
          </div>
          <div class="flex justify-between text-[10px] text-gray-400 mono">
            <span>Range: Low ₹{low:,.2f} / High ₹{high:,.2f}</span>
            <span>Outcome: {out}</span>
          </div>
        </div>
"""

        html_content += f"""
      </div>

      <!-- Desktop Wide Table -->
      <div class="hidden md:block overflow-x-auto">
        <table class="w-full text-left text-xs mono">
          <thead class="bg-[#0d1117] text-gray-400 uppercase text-[11px] border-b border-[#30363d]">
            <tr>
              <th class="px-4 py-3 font-sans">Stock</th>
              <th class="px-4 py-3">Direction</th>
              <th class="px-4 py-3">Qty</th>
              <th class="px-4 py-3">Entry Price</th>
              <th class="px-4 py-3">Day High</th>
              <th class="px-4 py-3">Day Low</th>
              <th class="px-4 py-3 text-amber-300">Exit Price</th>
              <th class="px-4 py-3">Outcome</th>
              <th class="px-4 py-3 text-right">Net P&L (₹)</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#30363d] text-gray-200">
"""
        for p in evaluated_picks:
            sym = p['symbol']
            dirn = p['direction']
            qty = p['qty']
            ent = p['entry']
            high = p['day_high']
            low = p['day_low']
            exit_p = p['exit_price']
            out = p['outcome']
            pnl = p['pnl']
            
            pnl_color = "text-emerald-400 font-bold" if pnl >= 0 else "text-rose-400 font-bold"
            pnl_sign = "+" if pnl >= 0 else ""
            badge = "text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-semibold" if "TARGET" in out else ("text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded font-semibold" if "LOSS" in out else "text-gray-300 bg-gray-800 px-2 py-0.5 rounded")
            dirn_color = "text-emerald-400 font-bold" if dirn == 'LONG' else "text-rose-400 font-bold"

            html_content += f"""
            <tr class="hover:bg-[#1f242c]">
              <td class="px-4 py-3 font-bold text-white text-sm font-sans">{sym}</td>
              <td class="px-4 py-3 {dirn_color}">{dirn}</td>
              <td class="px-4 py-3">{qty}</td>
              <td class="px-4 py-3">₹{ent:,.2f}</td>
              <td class="px-4 py-3 text-emerald-400">₹{high:,.2f}</td>
              <td class="px-4 py-3 text-rose-400">₹{low:,.2f}</td>
              <td class="px-4 py-3 text-amber-300 font-bold">₹{exit_p:,.2f}</td>
              <td class="px-4 py-3"><span class="{badge}">{out}</span></td>
              <td class="px-4 py-3 text-right {pnl_color} text-sm">{pnl_sign}₹{pnl:,.2f}</td>
            </tr>
"""

        html_content += f"""
          </tbody>
          <tfoot class="bg-[#0d1117] font-bold border-t border-[#30363d]">
            <tr>
              <td colspan="8" class="px-4 py-3 text-right text-gray-400 font-sans">TOTAL REALIZED NET P&L:</td>
              <td class="px-4 py-3 text-right {total_pnl_color} text-sm">{total_pnl_sign}₹{total_day_pnl:,.2f}</td>
            </tr>
          </tfoot>
        </table>
      </div>
"""
    else:
        html_content += """
      </div>
      <div class="text-center py-6 sm:py-8 text-gray-400 space-y-2">
        <i data-lucide="clock" class="w-7 h-7 sm:w-8 sm:h-8 mx-auto text-amber-400 mb-1"></i>
        <p class="text-xs sm:text-sm font-medium text-white">Market is currently LIVE</p>
        <p class="text-[11px] sm:text-xs text-gray-500">Official trade results and profit/loss calculation will appear automatically at 03:30 PM IST after market close.</p>
      </div>
"""

    html_content += f"""
    </div>

  </main>

  <!-- Footer -->
  <footer class="border-t border-[#30363d] py-4 text-center text-[11px] text-gray-500 space-y-0.5 px-3">
    <p class="text-gray-400 font-medium">NSE Intraday Breakout Terminal — Developed by Sanket Patel</p>
    <p>Data provided for quantitative intraday research. Always trade with strict risk management.</p>
  </footer>

  <script>
    lucide.createIcons();

    // Today's exact stock list loaded directly from server
    const currentStocks = {picks_js_data};
    let portfolioMode = 5; // 5 = All 5 stocks, 2 = Top 2 stocks

    function setPortfolioMode(mode) {{
      portfolioMode = mode;
      const btnAll5 = document.getElementById('btnAll5');
      const btnTop2 = document.getElementById('btnTop2');

      if (mode === 5) {{
        btnAll5.className = 'px-3 py-1 rounded bg-cyan-500 text-gray-950 font-bold transition-all';
        btnTop2.className = 'px-3 py-1 rounded text-gray-400 hover:text-white transition-all';
      }} else {{
        btnTop2.className = 'px-3 py-1 rounded bg-cyan-500 text-gray-950 font-bold transition-all';
        btnAll5.className = 'px-3 py-1 rounded text-gray-400 hover:text-white transition-all';
      }}
      recalculatePortfolio();
    }}

    function setQuickPreset(amount) {{
      document.getElementById('inputDematCash').value = amount;
      recalculatePortfolio();
    }}

    function recalculatePortfolio() {{
      const totalCash = parseFloat(document.getElementById('inputDematCash').value) || 0;
      if (totalCash <= 0 || !currentStocks || currentStocks.length === 0) return;

      const count = Math.min(portfolioMode, currentStocks.length);
      const activeStocks = currentStocks.slice(0, count);

      const marginPerStock = totalCash / count;
      const exposurePerStock = marginPerStock * 5.0; // 5x MIS Leverage
      const totalBuyingPower = totalCash * 5.0;

      document.getElementById('dispMarginPerStock').innerText = '₹' + Math.round(marginPerStock).toLocaleString('en-IN') + ' / stock';
      document.getElementById('dispTotalBuyingPower').innerText = '₹' + Math.round(totalBuyingPower).toLocaleString('en-IN') + ' (5x MIS)';

      const container = document.getElementById('portfolioAllocationContainer');
      let html = '';

      activeStocks.forEach((stk, idx) => {{
        const price = stk.entry;
        const shares = Math.max(1, Math.floor(exposurePerStock / price));
        const actualExposure = shares * price;
        const actualMargin = actualExposure / 5.0;

        let sl, t1, t2, maxLoss, profitT1, profitT2;
        const isLong = stk.direction === 'LONG';

        if (isLong) {{
          sl = price * 0.98;
          t1 = price * 1.03;
          t2 = price * 1.05;
          maxLoss = (price - sl) * shares;
          profitT1 = (t1 - price) * shares;
          profitT2 = (t2 - price) * shares;
        }} else {{
          sl = price * 1.02;
          t1 = price * 0.97;
          t2 = price * 0.95;
          maxLoss = (sl - price) * shares;
          profitT1 = (price - t1) * shares;
          profitT2 = (price - t2) * shares;
        }}

        const badgeClass = isLong ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border-rose-500/30';
        const dirLabel = isLong ? '🟢 BUY (LONG)' : '🔴 SELL (SHORT)';

        html += `
        <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-3 sm:p-4 space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-[#161b22] border border-[#30363d] flex items-center justify-center text-[10px] text-gray-400 font-mono font-bold">${{idx + 1}}</span>
              <h4 class="text-sm sm:text-base font-bold text-white font-sans">${{stk.symbol}}</h4>
              <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold border ${{badgeClass}}">${{dirLabel}}</span>
            </div>
            <div class="text-right">
              <span class="text-[10px] text-gray-400 block font-sans">Cash Margin</span>
              <span class="text-xs sm:text-sm font-bold text-cyan-300 mono">₹${{Math.round(actualMargin).toLocaleString('en-IN')}}</span>
            </div>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-[#161b22] p-2.5 rounded-lg mono text-center text-xs">
            <div class="p-1">
              <span class="text-[10px] text-cyan-400 block font-sans font-bold">SHARES TO TRADE</span>
              <span class="text-sm sm:text-base font-extrabold text-white">${{shares}} shares</span>
              <span class="text-[9px] text-gray-500 block">Val: ₹${{Math.round(actualExposure).toLocaleString('en-IN')}}</span>
            </div>
            <div class="p-1">
              <span class="text-[10px] text-rose-400 block font-sans font-semibold">STOP LOSS (-2%)</span>
              <span class="text-xs sm:text-sm font-bold text-rose-400">₹${{sl.toFixed(2)}}</span>
              <span class="text-[9px] text-rose-300/80 block">Max Loss: -₹${{Math.round(maxLoss).toLocaleString('en-IN')}}</span>
            </div>
            <div class="p-1">
              <span class="text-[10px] text-emerald-400 block font-sans font-semibold">TARGET 1 (+3%)</span>
              <span class="text-xs sm:text-sm font-bold text-emerald-400">₹${{t1.toFixed(2)}}</span>
              <span class="text-[9px] text-emerald-300/80 block">Profit: +₹${{Math.round(profitT1).toLocaleString('en-IN')}}</span>
            </div>
            <div class="p-1">
              <span class="text-[10px] text-cyan-400 block font-sans font-semibold">TARGET 2 (+5%)</span>
              <span class="text-xs sm:text-sm font-bold text-cyan-400">₹${{t2.toFixed(2)}}</span>
              <span class="text-[9px] text-cyan-300/80 block">Profit: +₹${{Math.round(profitT2).toLocaleString('en-IN')}}</span>
            </div>
          </div>
        </div>
        `;
      }});

      container.innerHTML = html;
    }}

    function calculateSingleStock(sym, price, dir) {{
      const el = document.getElementById('calculatorSection');
      if (el) el.scrollIntoView({{ behavior: 'smooth' }});
    }}

    // Initial run
    recalculatePortfolio();
  </script>
</body>
</html>
"""

    with open(os.path.join(docs_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Smart Demat Portfolio Allocator website generated successfully in {docs_dir}/index.html")
    return True

if __name__ == '__main__':
    generate_site()
