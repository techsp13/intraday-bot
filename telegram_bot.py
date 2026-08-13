import logging
import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config
import logger
import alerts
import main as main_orchestrator

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    msg = (
        "Welcome to the Intraday Stock Pick Bot! 🚀\n\n"
        "I provide daily breakout alerts and performance tracking.\n"
        "⚡ Send /stock to run a live scan and get today's stock picks instantly!\n"
        "Use /help to see all commands."
    )
    await update.message.reply_text(msg)

async def stock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stock or /scan command — triggers a live market scan on demand."""
    await update.message.reply_text("⚡ *Scanning live NSE market data...* Please wait ~10 seconds.", parse_mode='Markdown')
    
    try:
        # Run main pipeline in background thread to avoid blocking asyncio event loop
        loop = asyncio.get_running_loop()
        summary = await loop.run_in_executor(None, main_orchestrator.run_pipeline)
        
        picks_count = summary.get('total_picks', 0)
        if picks_count == 0:
            await update.message.reply_text("📭 No qualifying stock setups found right now (Market Regime / RS filter active).")
        else:
            await update.message.reply_text(f"✅ *Scan complete!* Sent {picks_count} stock picks with zoomed candlestick charts below.", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error running live market scan: `{e}`", parse_mode='Markdown')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    picks = logger.get_today_picks(today_str)
    
    if not picks:
        await update.message.reply_text(f"📭 No picks recorded for today ({today_str}). Send /stock to trigger a live scan!")
        return
        
    msg = f"📊 *Today's Status ({today_str})*\n━━━━━━━━━━━━━━━━━━━━━━━\n"
    total_pnl = 0.0
    
    for pick in picks:
        symbol = pick.get('symbol', 'UNKNOWN')
        status = pick.get('outcome', 'OPEN')
        pnl = pick.get('actual_pnl', 0.0) or 0.0
        total_pnl += pnl
        
        msg += f"▸ {symbol}: {status} (₹{pnl:.2f})\n"
        
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n💰 Running P&L: ₹{total_pnl:.2f}"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def weekly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /weekly command."""
    summary = logger.get_weekly_summary() if hasattr(logger, 'get_weekly_summary') else {}
    
    if not summary:
        await update.message.reply_text("📭 No data available for this week.")
        return
        
    msg = (
        f"📅 *Weekly Summary*\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"▸ Total P&L: ₹{summary.get('cumulative_pnl', 0.0):.2f}\n"
        f"▸ Win Rate:  {summary.get('win_rate', 0.0):.1f}%\n"
        f"▸ Avg R:     {summary.get('avg_r_multiple', 0.0):.2f}R\n"
        f"▸ Best Day:  {summary.get('best_day', 'N/A')}\n"
        f"▸ Worst Day: {summary.get('worst_day', 'N/A')}\n"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def picks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /picks command."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    picks = logger.get_today_picks(today_str)
    
    if not picks:
        await update.message.reply_text(f"📭 No picks recorded for today ({today_str}). Send /stock to run a live scan!")
        return
        
    msg = f"📋 *Detailed Picks ({today_str})*\n━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for pick in picks:
        symbol = pick.get('symbol', 'UNKNOWN')
        direction = pick.get('direction', 'LONG')
        entry = pick.get('entry', 0.0)
        sl = pick.get('sl', 0.0)
        t1 = pick.get('target1', 0.0)
        t2 = pick.get('target2', 0.0)
        outcome = pick.get('outcome', 'OPEN')
        pnl = pick.get('actual_pnl', 0.0) or 0.0
        
        msg += (
            f"*{symbol}* ({direction})\n"
            f"Entry: ₹{entry:.2f} | SL: ₹{sl:.2f} | T1: ₹{t1:.2f} | T2: ₹{t2:.2f}\n"
            f"Status: {outcome} | P&L: ₹{pnl:.2f}\n\n"
        )
        
    await update.message.reply_text(msg, parse_mode='Markdown')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    msg = (
        "🛠 *Available Commands*\n"
        "/stock - Run live market scan & get stock picks instantly!\n"
        "/scan - Trigger instant market scan\n"
        "/picks - View today's detailed stock picks\n"
        "/status - Today's picks & running P&L\n"
        "/weekly - Weekly performance summary\n"
        "/help - Show this help menu"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

def main():
    token = getattr(config, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in config.")
        return
        
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler('start', start_cmd))
    app.add_handler(CommandHandler('stock', stock_cmd))
    app.add_handler(CommandHandler('scan', stock_cmd))
    app.add_handler(CommandHandler('status', status_cmd))
    app.add_handler(CommandHandler('weekly', weekly_cmd))
    app.add_handler(CommandHandler('picks', picks_cmd))
    app.add_handler(CommandHandler('help', help_cmd))
    
    print('Telegram Bot Listener is running... Press Ctrl+C to stop.')
    app.run_polling()

if __name__ == '__main__':
    main()
