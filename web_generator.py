"""
Focused Current-Day Web Dashboard Generator for NSE Intraday Stock Pick Bot.
Features:
1. Morning 08:30 AM Stock Picks only.
2. Interactive Real-Time Stop Loss, Target 1, Target 2 & Position Size Calculator.
3. End-of-Day Market Close Results with explicit Actual Entry, Actual SL, Actual T1, Actual T2, and Actual Exit Price columns.
4. Clean, 100% current-day focused UI.
"""
import os
import json
import sqlite3
from datetime import datetime
import yfinance as yf
import pandas as pd

def generate_site():
    """Generates docs/index.html, docs/picks.json for GitHub Pages."""
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

    # Only take the morning batch (first 4-5 picks of the day)
    today_picks = today_picks[:5]

    # Fetch live / EOD actual price outcomes for today's stocks
    total_day_pnl = 0.0
    evaluated_picks = []
    
    for p in today_picks:
        symbol = p.get('symbol', 'STOCK')
        ticker = p.get('ticker', f"{symbol}.NS")
        entry = float(p.get('entry', 0.0))
        sl = float(p.get('sl', round(entry * 0.98, 2)))
        t1 = float(p.get('target1', round(entry * 1.03, 2)))
        t2 = float(p.get('target2', round(entry * 1.05, 2)))
        qty = int(p.get('position_size', 10))
        
        day_high, day_low, day_close = entry, entry, entry
        outcome = "🟡 OPEN / ACTIVE"
        exit_price = entry
        
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
                    outcome = "🟢 HIT TARGET 2 (+5.0%)"
                    exit_price = t2
                elif day_high >= t1:
                    outcome = "🟢 HIT TARGET 1 (+3.0%)"
                    exit_price = t1
                elif day_low <= sl:
                    outcome = "🔴 HIT STOP LOSS (-2.0%)"
                    exit_price = sl
                else:
                    outcome = "⚪ CLOSED AT 03:15 PM"
                    exit_price = day_close
        except Exception:
            pass

        pnl = round((exit_price - entry) * qty, 2)
        total_day_pnl += pnl
        
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

    # Save current day JSON
    with open(os.path.join(docs_dir, 'picks.json'), 'w') as f:
        json.dump(evaluated_picks, f, indent=2)

    now_formatted = datetime.now().strftime("%d-%b-%Y %I:%M %p IST")
    today_date_display = datetime.now().strftime("%d-%b-%Y")
    
    total_pnl_sign = "+" if total_day_pnl >= 0 else ""
    total_pnl_color = "text-emerald-400" if total_day_pnl >= 0 else "text-rose-400"

    html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NSE Intraday Terminal | Today's Picks ({today_date_display})</title>
  <meta name="description" content="Today's 08:30 AM NSE Intraday Stock Picks, Direct SL/T1/T2 Calculator & EOD Market Close Results">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          fontFamily: {{
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          }},
          colors: {{
            brand: {{
              dark: '#0B0F19',
              card: '#111827',
              border: '#1F2937',
              accent: '#10B981',
              cyan: '#06B6D4',
              rose: '#F43F5E'
            }}
          }}
        }}
      }}
    }}
  </script>
  <style>
    body {{ background-color: #0B0F19; color: #F3F4F6; }}
    .glass-card {{ background: rgba(17, 24, 39, 0.90); backdrop-filter: blur(12px); border: 1px solid #1F2937; }}
    .glass-card:hover {{ border-color: #374151; }}
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased selection:bg-emerald-500 selection:text-white">

  <!-- Sticky Top Navigation Header -->
  <header class="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <i data-lucide="trending-up" class="w-6 h-6 text-gray-950 stroke-[2.5]"></i>
        </div>
        <div>
          <h1 class="text-base sm:text-lg font-bold text-white flex items-center gap-2">
            NSE Intraday Terminal
            <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono font-semibold border border-emerald-500/20">TODAY'S SESSION</span>
          </h1>
          <p class="text-xs text-gray-400">08:30 AM Institutional Relative Strength Outperformance Picks</p>
        </div>
      </div>
      
      <div class="flex items-center space-x-3">
        <div class="hidden md:flex items-center gap-2 text-xs font-mono text-gray-400 bg-gray-950 px-3 py-1.5 rounded-lg border border-gray-800">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>{now_formatted}</span>
        </div>
        <a href="https://t.me/sany_trader_bot" target="_blank" class="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-md shadow-cyan-600/20 transition-all">
          <i data-lucide="send" class="w-3.5 h-3.5"></i>
          <span>Telegram Alerts</span>
        </a>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 w-full">

    <!-- Today's Session Hero Banner -->
    <div class="glass-card rounded-2xl p-6 relative overflow-hidden bg-gradient-to-r from-gray-900 via-gray-900/90 to-gray-950">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span class="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-md">
            📅 TRADING SESSION: {today_date_display}
          </span>
          <h2 class="text-2xl sm:text-3xl font-extrabold text-white mt-2">
            Today's 08:30 AM Actionable Stock Picks
          </h2>
          <p class="text-xs text-gray-400 mt-1 max-w-2xl">
            Generated at 08:30 AM IST. Enter at 09:15 AM Market Open. Pre-calculated 2.0% Stop Loss, 3.0% Target 1, and 5.0% Target 2. Square off at 03:15 PM.
          </p>
        </div>

        <div class="glass-card rounded-xl p-4 min-w-[220px] text-right border-gray-800 bg-gray-950/60">
          <span class="text-xs font-semibold text-gray-400 block uppercase tracking-wider">Today's Total Net P&L</span>
          <div class="text-2xl sm:text-3xl font-mono font-extrabold {total_pnl_color} mt-1">
            {total_pnl_sign}₹{total_day_pnl:,.2f}
          </div>
          <span class="text-[11px] text-gray-500 font-mono">100% Intraday MIS Realized</span>
        </div>
      </div>
    </div>

    <!-- Interactive SL / Target / Quantity Calculator -->
    <div class="glass-card rounded-2xl p-6 sm:p-7 border-cyan-500/30 shadow-xl shadow-cyan-950/20">
      <div class="flex items-center justify-between border-b border-gray-800 pb-3 mb-5">
        <div class="flex items-center gap-2">
          <div class="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <i data-lucide="calculator" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="text-lg font-bold text-white">Instant Trade Levels & Quantity Calculator</h3>
            <p class="text-xs text-gray-400">Enter stock buy price & quantity (or capital) for instant SL, T1, T2 and profit calculations</p>
          </div>
        </div>
        <span class="hidden sm:inline-block text-xs font-mono text-cyan-400 bg-cyan-500/10 px-2.5 py-1 rounded border border-cyan-500/20">
          AUTO-CALCULATING
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- Input Column -->
        <div class="space-y-4">
          <div>
            <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
              Stock Buy Price (₹)
            </label>
            <div class="relative">
              <span class="absolute left-3.5 top-2.5 text-gray-400 font-mono">₹</span>
              <input type="number" id="calcPrice" step="0.05" value="1250.00" oninput="calculateLevels()" class="w-full bg-gray-950 border border-gray-700 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 rounded-xl py-2.5 pl-8 pr-4 text-white font-mono font-bold text-base outline-none transition-all">
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                Quantity (Shares)
              </label>
              <input type="number" id="calcQty" value="16" oninput="calculateLevels()" class="w-full bg-gray-950 border border-gray-700 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 rounded-xl py-2.5 px-3.5 text-white font-mono font-bold text-base outline-none transition-all">
            </div>
            <div>
              <label class="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                Capital (₹)
              </label>
              <input type="number" id="calcCapital" value="100000" oninput="autoCalculateQty()" class="w-full bg-gray-950 border border-gray-700 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 rounded-xl py-2.5 px-3.5 text-white font-mono font-bold text-base outline-none transition-all">
            </div>
          </div>

          <p class="text-[11px] text-gray-500">
            💡 Risk is automatically capped at 1.0% (₹1,000 max loss per trade on ₹100k capital).
          </p>
        </div>

        <!-- Calculated Levels Output -->
        <div class="md:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-950/70 p-4 rounded-xl border border-gray-800 font-mono">
          <div class="p-3 bg-gray-900/90 rounded-lg border border-gray-800">
            <span class="text-[11px] font-sans text-rose-400 font-semibold block">STOP LOSS (-2.0%)</span>
            <div id="outSL" class="text-lg font-bold text-rose-400 mt-1">₹1,225.00</div>
            <span id="outRiskAmt" class="text-[10px] text-rose-300/80 block mt-0.5">Max Loss: -₹400</span>
          </div>

          <div class="p-3 bg-gray-900/90 rounded-lg border border-gray-800">
            <span class="text-[11px] font-sans text-emerald-400 font-semibold block">TARGET 1 (+3.0%)</span>
            <div id="outT1" class="text-lg font-bold text-emerald-400 mt-1">₹1,287.50</div>
            <span id="outProfitT1" class="text-[10px] text-emerald-300/80 block mt-0.5">Profit: +₹600</span>
          </div>

          <div class="p-3 bg-gray-900/90 rounded-lg border border-gray-800">
            <span class="text-[11px] font-sans text-cyan-400 font-semibold block">TARGET 2 (+5.0%)</span>
            <div id="outT2" class="text-lg font-bold text-cyan-400 mt-1">₹1,312.50</div>
            <span id="outProfitT2" class="text-[10px] text-cyan-300/80 block mt-0.5">Profit: +₹1,000</span>
          </div>

          <div class="p-3 bg-gray-900/90 rounded-lg border border-gray-800">
            <span class="text-[11px] font-sans text-gray-400 font-semibold block">TOTAL INVESTMENT</span>
            <div id="outTotalCost" class="text-lg font-bold text-white mt-1">₹20,000</div>
            <span class="text-[10px] text-gray-500 block mt-0.5">Risk-Reward: 1 : 2.5</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Today's 08:30 AM Actionable Stock Pick Cards -->
    <div class="space-y-4">
      <div class="flex items-center justify-between border-b border-gray-800 pb-2">
        <h3 class="text-lg font-bold text-white flex items-center gap-2">
          <i data-lucide="zap" class="w-5 h-5 text-emerald-400"></i>
          Today's 08:30 AM Morning Stock Picks ({len(evaluated_picks)} Stocks)
        </h3>
        <span class="text-xs text-gray-400 font-mono">Click 'Calculate' to load levels</span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
"""

    for p in evaluated_picks:
        symbol = p['symbol']
        direction = p['direction']
        entry = p['entry']
        sl = p['sl']
        t1 = p['target1']
        t2 = p['target2']
        qty = p['qty']
        rs = p['rs']
        outcome = p['outcome']
        pnl = p['pnl']

        html_content += f"""
        <div class="glass-card rounded-2xl p-5 relative overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-xl">
          <div class="flex items-start justify-between mb-3">
            <div>
              <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">{direction}</span>
              <h4 class="text-2xl font-mono font-extrabold text-white mt-1">{symbol}</h4>
            </div>
            <button onclick="setCalculator('{entry}', '{qty}')" class="px-2.5 py-1 rounded bg-gray-800 hover:bg-cyan-600 text-gray-300 hover:text-white text-[11px] font-semibold transition-all flex items-center gap-1">
              <i data-lucide="calculator" class="w-3 h-3"></i> Calculate
            </button>
          </div>

          <div class="space-y-2 py-2.5 border-y border-gray-800/80 font-mono text-xs">
            <div class="flex justify-between">
              <span class="text-gray-400 font-sans">Actual Entry:</span>
              <span class="text-white font-bold">₹{entry:,.2f}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-rose-400 font-sans">Actual SL (-2%):</span>
              <span class="text-rose-400 font-bold">₹{sl:,.2f}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-emerald-400 font-sans">Actual T1 (+3%):</span>
              <span class="text-emerald-400 font-bold">₹{t1:,.2f}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-cyan-400 font-sans">Actual T2 (+5%):</span>
              <span class="text-cyan-400 font-bold">₹{t2:,.2f}</span>
            </div>
          </div>

          <div class="mt-3 flex items-center justify-between text-[11px] font-mono text-gray-400">
            <span>Qty: <strong class="text-white">{qty}</strong></span>
            <span>RS: <strong class="text-emerald-400">+{rs:.1f}%</strong></span>
            <span>Risk: <strong class="text-rose-400">₹1,000</strong></span>
          </div>
        </div>
"""

    html_content += f"""
      </div>
    </div>

    <!-- End-of-Day Market Close Results Table with Explicit Price Levels -->
    <div class="space-y-4">
      <div class="flex items-center justify-between border-b border-gray-800 pb-2">
        <div>
          <h3 class="text-lg font-bold text-white flex items-center gap-2">
            <i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-400"></i>
            End-of-Day Market Close Results & Price Execution Log ({today_date_display})
          </h3>
          <p class="text-xs text-gray-400">Complete breakdown showing Actual Entry, SL, T1, T2, Day Range, Actual Exit Price & Realized P&L</p>
        </div>
      </div>

      <div class="glass-card rounded-2xl overflow-hidden shadow-2xl">
        <div class="overflow-x-auto">
          <table class="w-full text-left font-mono text-xs">
            <thead class="bg-gray-950 text-gray-400 uppercase tracking-wider text-[11px] border-b border-gray-800">
              <tr>
                <th class="px-4 py-3.5">Stock</th>
                <th class="px-4 py-3.5">Qty</th>
                <th class="px-4 py-3.5 text-white">Actual Entry</th>
                <th class="px-4 py-3.5 text-rose-400">Actual SL (-2%)</th>
                <th class="px-4 py-3.5 text-emerald-400">Actual T1 (+3%)</th>
                <th class="px-4 py-3.5 text-cyan-400">Actual T2 (+5%)</th>
                <th class="px-4 py-3.5">Day Low</th>
                <th class="px-4 py-3.5">Day High</th>
                <th class="px-4 py-3.5 text-amber-300 font-bold">Actual Exit Price</th>
                <th class="px-4 py-3.5">Status / Outcome</th>
                <th class="px-4 py-3.5 text-right font-bold">Net P&L (₹)</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-800/60 text-gray-300">
"""

    for p in evaluated_picks:
        sym = p['symbol']
        qty = p['qty']
        ent = p['entry']
        sl = p['sl']
        t1 = p['target1']
        t2 = p['target2']
        high = p['day_high']
        low = p['day_low']
        exit_p = p['exit_price']
        outcome = p['outcome']
        pnl = p['pnl']
        
        badge = "text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-bold border border-emerald-500/20" if "T" in outcome else ("text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded font-bold border border-rose-500/20" if "SL" in outcome else "text-gray-300 bg-gray-800 px-2 py-0.5 rounded")
        pnl_color = "text-emerald-400 font-bold" if pnl >= 0 else "text-rose-400 font-bold"
        pnl_sign = "+" if pnl >= 0 else ""

        html_content += f"""
              <tr class="hover:bg-gray-800/40 transition-colors">
                <td class="px-4 py-3.5 font-bold text-white text-sm">{sym}</td>
                <td class="px-4 py-3.5">{qty}</td>
                <td class="px-4 py-3.5 font-bold text-white">₹{ent:,.2f}</td>
                <td class="px-4 py-3.5 text-rose-400 font-semibold">₹{sl:,.2f}</td>
                <td class="px-4 py-3.5 text-emerald-400 font-semibold">₹{t1:,.2f}</td>
                <td class="px-4 py-3.5 text-cyan-400 font-semibold">₹{t2:,.2f}</td>
                <td class="px-4 py-3.5 text-rose-300">₹{low:,.2f}</td>
                <td class="px-4 py-3.5 text-emerald-300">₹{high:,.2f}</td>
                <td class="px-4 py-3.5 text-amber-300 font-extrabold text-sm">₹{exit_p:,.2f}</td>
                <td class="px-4 py-3.5"><span class="{badge}">{outcome}</span></td>
                <td class="px-4 py-3.5 text-right {pnl_color} text-sm">{pnl_sign}₹{pnl:,.2f}</td>
              </tr>
"""

    html_content += f"""
            </tbody>
            <tfoot class="bg-gray-950 font-bold text-sm border-t-2 border-gray-800">
              <tr>
                <td colspan="10" class="px-4 py-3.5 text-right text-gray-400 font-sans">TOTAL REALIZED NET P&L TODAY:</td>
                <td class="px-4 py-3.5 text-right {total_pnl_color}">{total_pnl_sign}₹{total_day_pnl:,.2f}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>

  </main>

  <!-- Footer -->
  <footer class="border-t border-gray-800 bg-gray-950 py-6 text-center text-xs text-gray-500">
    <div class="max-w-7xl mx-auto px-4">
      <p class="font-medium text-gray-400">NSE Intraday Breakout Bot — Current-Day Live Terminal</p>
      <p class="mt-1">All data updated automatically for {today_date_display}. Always trade with strict risk management.</p>
    </div>
  </footer>

  <script>
    lucide.createIcons();

    function setCalculator(price, qty) {{
      document.getElementById('calcPrice').value = price;
      document.getElementById('calcQty').value = qty;
      calculateLevels();
      window.scrollTo({{ top: 120, behavior: 'smooth' }});
    }}

    function autoCalculateQty() {{
      const price = parseFloat(document.getElementById('calcPrice').value) || 0;
      const capital = parseFloat(document.getElementById('calcCapital').value) || 100000;
      if (price <= 0) return;
      
      const maxRisk = capital * 0.01; // 1% risk = ₹1,000 on ₹100k
      const riskPerShare = price * 0.02; // 2% SL
      const calculatedQty = Math.max(1, Math.floor(maxRisk / riskPerShare));
      
      document.getElementById('calcQty').value = calculatedQty;
      calculateLevels();
    }}

    function calculateLevels() {{
      const price = parseFloat(document.getElementById('calcPrice').value) || 0;
      const qty = parseInt(document.getElementById('calcQty').value) || 1;

      if (price <= 0) return;

      const sl = price * 0.98;
      const t1 = price * 1.03;
      const t2 = price * 1.05;
      const totalCost = price * qty;
      const maxLoss = (price - sl) * qty;
      const profitT1 = (t1 - price) * qty;
      const profitT2 = (t2 - price) * qty;

      document.getElementById('outSL').innerText = '₹' + sl.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
      document.getElementById('outT1').innerText = '₹' + t1.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
      document.getElementById('outT2').innerText = '₹' + t2.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
      document.getElementById('outTotalCost').innerText = '₹' + totalCost.toLocaleString('en-IN', {{ maximumFractionDigits: 0 }});
      
      document.getElementById('outRiskAmt').innerText = 'Max Loss: -₹' + maxLoss.toLocaleString('en-IN', {{ maximumFractionDigits: 0 }});
      document.getElementById('outProfitT1').innerText = 'Profit: +₹' + profitT1.toLocaleString('en-IN', {{ maximumFractionDigits: 0 }});
      document.getElementById('outProfitT2').innerText = 'Profit: +₹' + profitT2.toLocaleString('en-IN', {{ maximumFractionDigits: 0 }});
    }}

    // Initial calculation on load
    calculateLevels();
  </script>
</body>
</html>
"""

    with open(os.path.join(docs_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Current-day focused dashboard with explicit actual price levels generated successfully in {docs_dir}/index.html")
    return True

if __name__ == '__main__':
    generate_site()
