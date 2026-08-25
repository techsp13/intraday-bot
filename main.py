import sys
import time
import traceback
import io
from datetime import datetime

# Fix Windows console encoding for ₹ and other Unicode characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import config
import data_fetcher
import screener
import risk_manager
import logger
import alerts
import web_generator
import nse_holidays

def run_pipeline(dry_run: bool = False, top2_only: bool = False):
    """Run the complete intraday stock pick pipeline."""
    start_time = time.time()
    mode_label = "09:00 AM Top 2 Filtered Picks" if top2_only else "08:30 AM Full Watchlist"
    print(f'=== Intraday Stock Pick Bot ({mode_label}) ===')
    print(f'Date: {datetime.now().strftime("%d-%b-%Y %H:%M")} IST')
    print(f'Capital: ₹{getattr(config, "CAPITAL_BASE", 100000):,.0f}')
    print()
    
    try:
        # Step 0: Check NSE Trading Holiday & Weekend
        is_closed, holiday_reason = nse_holidays.is_market_holiday()
        if is_closed and not dry_run:
            print(f'MARKET CLOSED: {holiday_reason}. Skipping scan, Telegram alerts, and website update.')
            return

        # Step 1: Check daily loss limit
        tracker = risk_manager.DailyRiskTracker()
        today_str = datetime.now().strftime('%Y-%m-%d')
        is_halted, cum_pnl = tracker.is_daily_limit_hit(today_str)
        if is_halted:
            print(f'HALTED: Daily loss limit hit (P&L: ₹{cum_pnl:,.2f})')
            if not dry_run:
                alerts.send_daily_loss_halt_alert(cum_pnl)
            return
        
        # Step 2: Load watchlist
        print('Loading watchlist...')
        symbols = data_fetcher.load_watchlist()
        print(f'Watchlist: {len(symbols)} symbols')
        
        # Step 3: Fetch data
        print('Fetching intraday data...')
        intraday_data = data_fetcher.fetch_intraday_data(symbols)
        print(f'Got intraday data for {len(intraday_data)} symbols')
        
        print('Fetching daily data...')
        daily_data = data_fetcher.fetch_daily_data(symbols)
        print(f'Got daily data for {len(daily_data)} symbols')
        
        # Step 4: Compute volume/turnover baselines
        print('Computing baselines...')
        avg_volumes = {}
        avg_turnovers = {}
        for sym in symbols:
            if sym in daily_data and not daily_data[sym].empty:
                avg_volumes[sym] = data_fetcher.compute_avg_daily_volume(daily_data[sym])
                avg_turnovers[sym] = data_fetcher.compute_avg_daily_turnover(daily_data[sym])
        
        # Step 5: Run screener
        print('Running screener...')
        raw_picks = screener.scan_all(intraday_data, daily_data, avg_volumes, avg_turnovers, top2_only=top2_only)
        print(f'Screener found {len(raw_picks)} raw picks')
        
        # Step 6: Risk management
        sized_picks = risk_manager.enrich_picks(raw_picks, getattr(config, 'CAPITAL_BASE', 100000))
        print(f'After risk filters: {len(sized_picks)} picks')
        
        # Step 7: Log picks
        if sized_picks:
            logger.log_picks(sized_picks)
            print(f'Logged {len(sized_picks)} picks to SQLite')
        
        # Step 8: Send alerts
        if dry_run:
            print('\n--- DRY RUN (no Telegram alerts) ---')
            for p in sized_picks:
                print(f"  {p.get('direction', 'LONG')} {p.get('symbol', 'UNKNOWN')} @ ₹{p.get('entry', 0.0):.2f} | SL: ₹{p.get('sl', 0.0):.2f} | T1: ₹{p.get('target1', 0.0):.2f} | Score: {p.get('score', 0)}")
        else:
            if sized_picks:
                alert_type = 'top2' if top2_only else 'watchlist'
                sent = alerts.send_picks_batch(sized_picks, alert_type=alert_type)
                print(f'Sent {sent} alerts to Telegram ({alert_type})')
            else:
                alerts.send_no_picks_alert()
                print('No picks — sent notification')

        # Step 9: Update Web Dashboard & JSON API
        try:
            web_generator.generate_site()
        except Exception as e:
            print(f'Warning: Web generation failed: {e}')
                
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"\nCRITICAL ERROR:\n{error_msg}")
        if not dry_run:
            alerts.send_error_alert(f"Pipeline Exception: {e}")
            
    finally:
        elapsed = time.time() - start_time
        print(f'\nPipeline completed in {elapsed:.1f}s')

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    top2_only = '--top2' in sys.argv or ('--watchlist' not in sys.argv and datetime.now().hour == 9 and datetime.now().minute < 15)
    run_pipeline(dry_run=dry_run, top2_only=top2_only)
