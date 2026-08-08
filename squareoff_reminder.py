"""
Square-off reminder and end-of-day outcome checker.
Run at ~3:15 PM IST via GitHub Actions.
"""
import sys
from datetime import datetime

import config
import logger
import alerts

def run_squareoff():
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f'=== Square-Off Reminder ===')
    print(f'Date: {today_str}')
    
    # Get today's picks
    picks = logger.get_today_picks(today_str)
    
    if picks:
        # Send squareoff reminder
        alerts.send_squareoff_reminder(picks)
        print(f'Sent square-off reminder for {len(picks)} picks')
        
        # Run EOD outcome check
        print('Checking outcomes...')
        try:
            logger.update_outcomes_eod(today_str)
            print('Outcomes updated')
        except Exception as e:
            print(f'Error updating outcomes: {e}')
            alerts.send_error_alert(f'EOD outcome check failed: {e}')
        
        # Compute and send daily summary
        summary = logger.compute_daily_summary(today_str)
        if summary:
            alerts.send_daily_summary_alert(summary)
            print(f'Daily summary: Win rate {summary.get("win_rate", 0):.1f}%, P&L ₹{summary.get("daily_pnl", 0):,.2f}')
    else:
        print('No picks today — nothing to square off')
    
    print('Done.')

if __name__ == '__main__':
    try:
        run_squareoff()
    except Exception as e:
        print(f'Fatal error: {e}')
        import traceback
        traceback.print_exc()
        try:
            alerts.send_error_alert(str(e))
        except:
            pass
        sys.exit(1)
