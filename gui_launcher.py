"""
Sleek Desktop GUI Application & Launcher for NSE Intraday Stock Pick Bot.
Provides 1-click execution for Live Market Scan, Telegram Bot Listener, and Today's Stock Picks display.
"""
import sys
import os
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Ensure working directory is set to app root
app_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir)
sys.path.insert(0, app_dir)

import main as main_orchestrator
import logger
from datetime import datetime

class IntradayBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NSE Intraday Stock Pick Bot 🚀")
        self.root.geometry("780x560")
        self.root.configure(bg="#0E1621")

        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#0E1621")
        style.configure("TLabel", background="#0E1621", foreground="#FFFFFF", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#00E676")
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background="#1F4E78", foreground="#FFFFFF")
        style.map("TButton", background=[("active", "#29B6F6")])

        # Header Frame
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(header_frame, text="🚀 NSE INTRADAY STOCK PICK BOT", style="Header.TLabel")
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(header_frame, text="NIFTY Relative Strength Outperformance Strategy + Market Regime Filter", font=("Segoe UI", 9), foreground="#8E99A2")
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Control Buttons Frame
        btn_frame = ttk.Frame(self.root, padding=15)
        btn_frame.pack(fill=tk.X)

        self.run_btn = tk.Button(
            btn_frame, 
            text="⚡ RUN LIVE MARKET SCAN NOW", 
            command=self.start_scan_thread,
            bg="#00E676", 
            fg="#0E1621", 
            font=("Segoe UI", 11, "bold"),
            activebackground="#B2FF59",
            padx=15, 
            pady=8,
            cursor="hand2"
        )
        self.run_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.bot_btn = tk.Button(
            btn_frame, 
            text="🤖 START TELEGRAM BOT LISTENER", 
            command=self.start_bot_listener,
            bg="#29B6F6", 
            fg="#0E1621", 
            font=("Segoe UI", 11, "bold"),
            activebackground="#80D8FF",
            padx=15, 
            pady=8,
            cursor="hand2"
        )
        self.bot_btn.pack(side=tk.LEFT)

        # Output Log Box
        log_frame = ttk.Frame(self.root, padding=15)
        log_frame.pack(fill=tk.BOTH, expand=True)

        log_lbl = ttk.Label(log_frame, text="📋 Execution Output & Picks Log:", font=("Segoe UI", 10, "bold"))
        log_lbl.pack(anchor="w", pady=(0, 5))

        self.log_box = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD, 
            bg="#17212B", 
            fg="#00E676", 
            font=("Consolas", 10),
            insertbackground="#FFFFFF",
            relief=tk.FLAT
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)

        self.log("Ready. Click 'RUN LIVE MARKET SCAN NOW' to scan NIFTY 500 stocks & send Telegram alerts.\n" + "━"*60)

    def log(self, text):
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)

    def start_scan_thread(self):
        self.run_btn.config(state=tk.DISABLED, bg="#555555")
        self.log("\n[⚡ STARTING LIVE MARKET SCAN...]")
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        try:
            summary = main_orchestrator.run_pipeline()
            picks_count = summary.get('total_picks', 0)
            pnl = summary.get('daily_pnl', 0.0)

            self.log(f"✅ Live scan completed!")
            self.log(f"▸ Total Picks Found: {picks_count}")
            self.log(f"▸ Daily Running P&L: Rs. {pnl:,.2f}")
            self.log("▸ All stock picks + zoomed 5m candlestick charts sent to Telegram!")
            self.log("━"*60)
        except Exception as e:
            self.log(f"⚠️ Error running scan: {e}")
        finally:
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL, bg="#00E676"))

    def start_bot_listener(self):
        self.log("\n[🤖 STARTING TELEGRAM BOT LISTENER (Interactive Commands Active)...]")
        try:
            subprocess.Popen([sys.executable, "telegram_bot.py"], cwd=app_dir)
            self.log("✅ Telegram Bot listener launched in background. Try sending /stock on Telegram!")
        except Exception as e:
            self.log(f"⚠️ Error launching bot listener: {e}")

def main():
    root = tk.Tk()
    app = IntradayBotGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
