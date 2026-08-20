"""
Clean, Simple & Mobile-Optimized Web Dashboard Generator for NSE Intraday Stock Pick Bot.
- 100% Mobile Friendly: Zero horizontal scrolling on smartphones.
- Adaptive UI: Modern Stacked Cards on Mobile + Clean Table on Desktop.
- Developed by Sanket Patel.
- Investment Amount & Position Size Calculator.
- Trading Rules & Selection Guide.
- Market Close Results & P&L reveal at 03:30 PM.
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
    
    picks = []
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM picks ORDER BY date DESC, id DESC")
            rows = c.fetchall()
            for r in rows:
                picks.append(dict(r))
            conn.close()
        except Exception as e:
            print(f"Error reading database: {e}")

    # Today's picks (or latest trading day)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_picks = [p for p in picks if p.get('date') == today_str]
    if not today_picks and picks:
        latest_date = picks[0].get('date')
        today_picks = [p for p in picks if p.get('date') == latest_date]
        today_str = latest_date or today_str

    # Lock to original morning 08:30 AM picks (deduplicate symbols)
    seen_symbols = set()
    deduped_today_picks = []
    for p in reversed(today_picks):
        sym = p.get('symbol')
        if sym and sym not in seen_symbols:
            seen_symbols.add(sym)
            deduped_today_picks.append(p)
    today_picks = list(reversed(deduped_today_picks))[:5]

    # Check if current time is after 03:30 PM IST
    now = datetime.now()
    is_market_closed = (now.hour > 15) or (now.hour == 15 and now.minute >= 30)
    
    evaluated_picks = []
    total_day_pnl = 0.0

    for p in today_picks:
        symbol = p.get('symbol', 'STOCK')
        ticker = p.get('ticker', f"{symbol}.NS")
        entry = float(p.get('entry', 0.0))
        sl = float(p.get('sl', round(entry * 0.98, 2)))
        t1 = float(p.get('target1', round(entry * 1.03, 2)))
        t2 = float(p.get('target2', round(entry * 1.05, 2)))
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
            except Exception:
                pass

            pnl = round((exit_price - entry) * qty, 2)
            total_day_pnl += pnl
        else:
            pnl = 0.0

        evaluated_picks.append({
            'symbol': symbol,
            'direction': p.get('direction', 'LONG'),
            'entry': entry,
            'sl': sl,
            'target1': t1,
            'target2': t2,
            'qty': qty,
            'rs': float(p.get('adx', 0.0)),
            'day_high': day_high,
            'day_low': day_low,
            'day_close': day_close,
            'exit_price': exit_price,
            'outcome': outcome,
            'pnl': pnl
        })

    # Save JSON API
    with open(os.path.join(docs_dir, 'picks.json'), 'w') as f:
        json.dump(evaluated_picks, f, indent=2)

    now_formatted = datetime.now().strftime("%d-%b-%Y %I:%M %p IST")
    today_date_display = datetime.now().strftime("%d-%b-%Y")
    
    total_pnl_sign = "+" if total_day_pnl >= 0 else ""
    total_pnl_color = "text-emerald-400" if total_day_pnl >= 0 else "text-rose-400"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>NSE Intraday Terminal | Developed by Sanket Patel</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
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

  <!-- Mobile-Optimized Header -->
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
        <i data-lucide="send" class="w-3.5 h-3.5"></i> <span class="hidden xs:inline">Telegram</span>
      </a>
    </div>
  </header>

  <!-- Main Content Container -->
  <main class="flex-1 max-w-6xl mx-auto w-full px-3 py-4 sm:px-4 sm:py-6 space-y-5">

    <!-- Section 1: Morning Stock Picks (Responsive Cards on Mobile / Table on Desktop) -->
    <div class="card rounded-xl p-4 sm:p-5 shadow-lg">
      <div class="flex items-center justify-between border-b border-[#30363d] pb-3 mb-4">
        <div>
          <h2 class="text-base sm:text-lg font-bold text-white flex items-center gap-2">
            <i data-lucide="zap" class="w-4 h-4 sm:w-5 sm:h-5 text-amber-400"></i>
            Today's 08:30 AM Stock Picks
          </h2>
          <p class="text-[11px] sm:text-xs text-gray-400">Buy at 09:15 AM Market Open | Set Stop Loss & Targets</p>
        </div>
        <span class="text-[11px] px-2 py-0.5 rounded bg-[#0d1117] text-gray-300 border border-[#30363d] mono">
          {len(evaluated_picks)} Stocks
        </span>
      </div>

      <!-- MOBILE VIEW: Stacked Clean Cards (Zero Horizontal Scroll!) -->
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

        html_content += f"""
        <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-3.5 space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <h3 class="text-lg font-bold text-white font-sans">{sym}</h3>
              <span class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">{dirn}</span>
            </div>
            <button onclick="setCalculator('{ent}', '{qty}')" class="px-3 py-1 rounded bg-[#21262d] hover:bg-cyan-600 text-cyan-400 hover:text-white text-xs font-semibold flex items-center gap-1 transition-colors">
              <i data-lucide="calculator" class="w-3 h-3"></i> Calculate
            </button>
          </div>

          <div class="grid grid-cols-2 gap-2 bg-[#161b22] p-2.5 rounded-lg mono text-xs">
            <div>
              <span class="text-[10px] text-gray-400 block font-sans">Buy Price</span>
              <span class="text-white font-bold text-sm">₹{ent:,.2f}</span>
            </div>
            <div>
              <span class="text-[10px] text-rose-400 block font-sans">Stop Loss (-2%)</span>
              <span class="text-rose-400 font-bold text-sm">₹{sl:,.2f}</span>
            </div>
            <div>
              <span class="text-[10px] text-emerald-400 block font-sans">Target 1 (+3%)</span>
              <span class="text-emerald-400 font-bold text-sm">₹{t1:,.2f}</span>
            </div>
            <div>
              <span class="text-[10px] text-cyan-400 block font-sans">Target 2 (+5%)</span>
              <span class="text-cyan-400 font-bold text-sm">₹{t2:,.2f}</span>
            </div>
          </div>
          
          <div class="flex items-center justify-between text-[11px] text-gray-400 mono pt-1 border-t border-[#30363d]/60">
            <span>Recommended Qty: <strong class="text-white">{qty} shares</strong></span>
            <span>Est. Cost: <strong class="text-gray-300">₹{int(ent*qty):,}</strong></span>
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
              <th class="px-4 py-3 text-white">Buy Price</th>
              <th class="px-4 py-3 text-rose-400">Stop Loss (-2%)</th>
              <th class="px-4 py-3 text-emerald-400">Target 1 (+3%)</th>
              <th class="px-4 py-3 text-cyan-400">Target 2 (+5%)</th>
              <th class="px-4 py-3">Shares</th>
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
        qty = p['qty']

        html_content += f"""
            <tr class="hover:bg-[#1f242c] transition-colors">
              <td class="px-4 py-3.5 font-bold text-white text-sm font-sans">{sym}</td>
              <td class="px-4 py-3.5 text-emerald-400 font-bold">{dirn}</td>
              <td class="px-4 py-3.5 font-bold text-white">₹{ent:,.2f}</td>
              <td class="px-4 py-3.5 text-rose-400 font-semibold">₹{sl:,.2f}</td>
              <td class="px-4 py-3.5 text-emerald-400 font-semibold">₹{t1:,.2f}</td>
              <td class="px-4 py-3.5 text-cyan-400 font-semibold">₹{t2:,.2f}</td>
              <td class="px-4 py-3.5 font-bold">{qty}</td>
              <td class="px-4 py-3.5 text-right">
                <button onclick="setCalculator('{ent}', '{qty}')" class="px-2.5 py-1 rounded bg-[#21262d] hover:bg-cyan-600 text-gray-300 hover:text-white text-[11px] font-sans font-semibold transition-colors">
                  Calculate
                </button>
              </td>
            </tr>
"""

    html_content += f"""
          </tbody>
        </table>
      </div>
    </div>

    <!-- Section 2: Direct Investment Amount & Shares Calculator -->
    <div class="card rounded-xl p-4 sm:p-5 border-cyan-500/40 shadow-lg">
      <div class="flex items-center gap-2 border-b border-[#30363d] pb-3 mb-4">
        <i data-lucide="calculator" class="w-5 h-5 text-cyan-400"></i>
        <div>
          <h3 class="text-sm sm:text-base font-bold text-white">Investment & Position Size Calculator</h3>
          <p class="text-[11px] sm:text-xs text-gray-400">Enter your Total Investment Amount to find exact shares & levels</p>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-4">
        <!-- Input 1: Buy Price -->
        <div>
          <label class="block text-xs text-gray-400 mb-1 font-semibold">Stock Buy Price (₹)</label>
          <input type="number" id="calcPrice" step="0.05" value="1250.00" oninput="onPriceOrInvestmentChange()" class="w-full bg-[#0d1117] border border-[#30363d] focus:border-cyan-400 rounded-lg p-2.5 text-white mono font-bold text-base outline-none">
        </div>

        <!-- Input 2: Total Investment Amount -->
        <div>
          <label class="block text-xs text-cyan-400 mb-1 font-semibold">Total Amount to Invest (₹)</label>
          <input type="number" id="calcInvestment" step="1000" value="20000" oninput="onInvestmentChange()" class="w-full bg-[#0d1117] border border-cyan-500/50 focus:border-cyan-400 rounded-lg p-2.5 text-cyan-300 mono font-bold text-base outline-none">
        </div>

        <!-- Input 3: Quantity (Shares) -->
        <div>
          <label class="block text-xs text-gray-400 mb-1 font-semibold">Quantity (Shares to Buy)</label>
          <input type="number" id="calcQty" value="16" oninput="onQtyChange()" class="w-full bg-[#0d1117] border border-[#30363d] focus:border-cyan-400 rounded-lg p-2.5 text-white mono font-bold text-base outline-none">
        </div>
      </div>

      <!-- Mobile-Friendly 2x2 Grid Output -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 bg-[#0d1117] p-3 rounded-xl border border-[#30363d] mono text-center">
        <div class="p-2 bg-[#161b22] rounded-lg border border-[#30363d]">
          <span class="text-[10px] sm:text-[11px] text-gray-400 block font-sans">TOTAL INVESTED</span>
          <div id="outTotalInvested" class="text-sm sm:text-base font-bold text-white mt-0.5">₹20,000</div>
          <span id="outShareCount" class="text-[10px] text-gray-500 font-sans block">16 shares</span>
        </div>

        <div class="p-2 bg-[#161b22] rounded-lg border border-[#30363d]">
          <span class="text-[10px] sm:text-[11px] text-rose-400 block font-sans">STOP LOSS (-2%)</span>
          <div id="outSL" class="text-sm sm:text-base font-bold text-rose-400 mt-0.5">₹1,225.00</div>
          <span id="outRiskAmt" class="text-[10px] text-rose-300/80 font-sans block">Loss: -₹400</span>
        </div>

        <div class="p-2 bg-[#161b22] rounded-lg border border-[#30363d]">
          <span class="text-[10px] sm:text-[11px] text-emerald-400 block font-sans">TARGET 1 (+3%)</span>
          <div id="outT1" class="text-sm sm:text-base font-bold text-emerald-400 mt-0.5">₹1,287.50</div>
          <span id="outProfitT1" class="text-[10px] text-emerald-300/80 font-sans block">Profit: +₹600</span>
        </div>

        <div class="p-2 bg-[#161b22] rounded-lg border border-[#30363d]">
          <span class="text-[10px] sm:text-[11px] text-cyan-400 block font-sans">TARGET 2 (+5%)</span>
          <div id="outT2" class="text-sm sm:text-base font-bold text-cyan-400 mt-0.5">₹1,312.50</div>
          <span id="outProfitT2" class="text-[10px] text-cyan-300/80 font-sans block">Profit: +₹1,000</span>
        </div>
      </div>
    </div>

    <!-- Section 3: Trading Rules & Stock Selection Guide -->
    <div class="card rounded-xl p-4 sm:p-5 shadow-lg border-emerald-500/30">
      <div class="flex items-center gap-2 border-b border-[#30363d] pb-3 mb-4">
        <i data-lucide="book-open" class="w-5 h-5 text-emerald-400"></i>
        <div>
          <h3 class="text-sm sm:text-base font-bold text-white">How to Trade & Select the Best Stocks</h3>
          <p class="text-[11px] sm:text-xs text-gray-400">Simple 4-step rules to pick winning setups and protect capital</p>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        
        <!-- How to Pick the Best Stock -->
        <div class="space-y-2.5 bg-[#0d1117] p-3.5 rounded-xl border border-[#30363d]">
          <h4 class="font-bold text-cyan-400 text-xs sm:text-sm flex items-center gap-1.5">
            <i data-lucide="check-circle" class="w-4 h-4 text-cyan-400"></i>
            How to Choose from the 4-5 Stocks:
          </h4>
          
          <div class="space-y-2 text-gray-300 text-[11px] sm:text-xs">
            <div class="flex items-start gap-2">
              <span class="font-bold text-emerald-400 shrink-0">1.</span>
              <p><strong class="text-white">Buy Only Green Openers:</strong> At 09:15 AM, check which stocks open in <span class="text-emerald-400 font-semibold">GREEN</span> (ticking higher than open). Avoid stocks that open Red.</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-amber-400 shrink-0">2.</span>
              <p><strong class="text-white">Skip Big Gap-Ups (> +2%):</strong> If a stock opens +2% higher, skip it to avoid morning profit-taking pullbacks. Look for flat or small (+0.5% to +1%) opens.</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-cyan-400 shrink-0">3.</span>
              <p><strong class="text-white">Split into Top 2 Stocks:</strong> Divide your budget equally into the top 2 green stocks to catch big +5% runner trends.</p>
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
              <p><strong class="text-white">09:15 AM Entry:</strong> Place market or limit orders at open. Calculate quantity using the calculator above.</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-rose-400 shrink-0">B.</span>
              <p><strong class="text-white">Strict 2.0% Stop Loss:</strong> Always place your SL order immediately. Never hold below -2% (capital protection).</p>
            </div>

            <div class="flex items-start gap-2">
              <span class="font-bold text-purple-400 shrink-0">C.</span>
              <p><strong class="text-white">03:15 PM Square-off:</strong> Exit all remaining open positions before 03:30 PM. 100% intraday with zero overnight risk.</p>
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

            html_content += f"""
        <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-3 space-y-2">
          <div class="flex items-center justify-between">
            <h4 class="font-bold text-white text-base font-sans">{sym}</h4>
            <span class="{badge}">{out}</span>
          </div>
          <div class="grid grid-cols-3 gap-2 bg-[#161b22] p-2 rounded-lg mono text-[11px] text-center">
            <div>
              <span class="text-[9px] text-gray-400 block font-sans">Buy Price</span>
              <span class="text-white font-semibold">₹{ent:,.2f}</span>
            </div>
            <div>
              <span class="text-[9px] text-amber-300 block font-sans">Exit Price</span>
              <span class="text-amber-300 font-bold">₹{exit_p:,.2f}</span>
            </div>
            <div>
              <span class="text-[9px] text-gray-400 block font-sans">Net P&L</span>
              <span class="{pnl_color} text-xs">{pnl_sign}₹{pnl:,.2f}</span>
            </div>
          </div>
          <div class="flex justify-between text-[10px] text-gray-400 mono">
            <span>Range: Low ₹{low:,.2f} / High ₹{high:,.2f}</span>
            <span>Qty: {qty}</span>
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
              <th class="px-4 py-3">Qty</th>
              <th class="px-4 py-3">Buy Price</th>
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

            html_content += f"""
            <tr class="hover:bg-[#1f242c]">
              <td class="px-4 py-3 font-bold text-white text-sm font-sans">{sym}</td>
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
              <td colspan="7" class="px-4 py-3 text-right text-gray-400 font-sans">TOTAL REALIZED NET P&L:</td>
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

    html_content += """
    </div>

  </main>

  <!-- Simple Footer -->
  <footer class="border-t border-[#30363d] py-4 text-center text-[11px] text-gray-500 space-y-0.5 px-3">
    <p class="text-gray-400 font-medium">NSE Intraday Breakout Terminal — Developed by Sanket Patel</p>
    <p>Data provided for quantitative intraday research. Always trade with strict risk management.</p>
  </footer>

  <script>
    lucide.createIcons();

    function setCalculator(price, qty) {
      document.getElementById('calcPrice').value = price;
      const invest = parseFloat(document.getElementById('calcInvestment').value) || 20000;
      const p = parseFloat(price) || 1;
      const shares = Math.max(1, Math.floor(invest / p));
      document.getElementById('calcQty').value = shares;
      updateCalculations(p, shares);
      window.scrollTo({ top: 280, behavior: 'smooth' });
    }

    function onInvestmentChange() {
      const invest = parseFloat(document.getElementById('calcInvestment').value) || 0;
      const price = parseFloat(document.getElementById('calcPrice').value) || 1;
      if (price > 0 && invest > 0) {
        const shares = Math.max(1, Math.floor(invest / price));
        document.getElementById('calcQty').value = shares;
        updateCalculations(price, shares);
      }
    }

    function onQtyChange() {
      const price = parseFloat(document.getElementById('calcPrice').value) || 0;
      const qty = parseInt(document.getElementById('calcQty').value) || 1;
      if (price > 0 && qty > 0) {
        document.getElementById('calcInvestment').value = Math.round(price * qty);
        updateCalculations(price, qty);
      }
    }

    function onPriceOrInvestmentChange() {
      onInvestmentChange();
    }

    function updateCalculations(price, qty) {
      if (price <= 0 || qty <= 0) return;

      const sl = price * 0.98;
      const t1 = price * 1.03;
      const t2 = price * 1.05;
      const totalInvested = price * qty;
      const maxLoss = (price - sl) * qty;
      const profitT1 = (t1 - price) * qty;
      const profitT2 = (t2 - price) * qty;

      document.getElementById('outTotalInvested').innerText = '₹' + Math.round(totalInvested).toLocaleString('en-IN');
      document.getElementById('outShareCount').innerText = qty + ' shares';

      document.getElementById('outSL').innerText = '₹' + sl.toFixed(2);
      document.getElementById('outRiskAmt').innerText = 'Loss: -₹' + Math.round(maxLoss).toLocaleString('en-IN');

      document.getElementById('outT1').innerText = '₹' + t1.toFixed(2);
      document.getElementById('outProfitT1').innerText = 'Profit: +₹' + Math.round(profitT1).toLocaleString('en-IN');

      document.getElementById('outT2').innerText = '₹' + t2.toFixed(2);
      document.getElementById('outProfitT2').innerText = 'Profit: +₹' + Math.round(profitT2).toLocaleString('en-IN');
    }

    // Initial run
    onInvestmentChange();
  </script>
</body>
</html>
"""

    with open(os.path.join(docs_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"100% Mobile-Friendly website generated successfully in {docs_dir}/index.html")
    return True

if __name__ == '__main__':
    generate_site()
