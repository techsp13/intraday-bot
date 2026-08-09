"""
Export ALL 1,254 Trades Over 3 Full Years (2023-2026) to CSV and Excel
Uses 3-year daily dataset (period="3y", interval="1d") matching report_rs_3year.py.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from data_fetcher import load_watchlist

def export_full_3year_trades():
    symbols = load_watchlist()[:100]
    all_tickers = symbols + ['^NSEI']
    print("=== EXPORTING FULL 3-YEAR (1254 TRADES) LOG TO CSV & EXCEL ===")
    print("Downloading 3-year daily market data...")

    df_daily = yf.download(all_tickers, period="3y", interval="1d", progress=False, group_by="ticker")

    if '^NSEI' not in df_daily.columns.levels[0]:
        print("Nifty index data missing")
        return

    nifty_df = df_daily['^NSEI'].dropna(subset=['Open', 'High', 'Low', 'Close'])
    nifty_df.index = nifty_df.index.tz_localize(None) if nifty_df.index.tz is not None else nifty_df.index

    nifty_df['Nifty_EMA20'] = nifty_df['Close'].ewm(span=20, adjust=False).mean()
    nifty_df['Nifty_EMA50'] = nifty_df['Close'].ewm(span=50, adjust=False).mean()
    nifty_df['Nifty_5d_Ret'] = nifty_df['Close'].pct_change(5) * 100.0

    capital = 100000.0
    running_capital = capital
    trades = []

    trading_dates = sorted(list(set(nifty_df.index.date)))[50:]

    for t_date in trading_dates:
        t_ts = pd.Timestamp(t_date)
        if t_ts not in nifty_df.index: continue

        nifty_row = nifty_df.loc[t_ts]

        # REGIME FILTER: Pause buys when Nifty 20 EMA <= 50 EMA
        if nifty_row['Nifty_EMA20'] <= nifty_row['Nifty_EMA50']:
            continue

        nifty_5d_ret = nifty_row['Nifty_5d_Ret']
        if pd.isna(nifty_5d_ret): continue

        stock_rs = []

        for symbol in symbols:
            try:
                s_df = df_daily[symbol].dropna(subset=['Open', 'High', 'Low', 'Close']) if isinstance(df_daily.columns, pd.MultiIndex) else df_daily
                s_df.index = s_df.index.tz_localize(None) if s_df.index.tz is not None else s_df.index

                if t_ts not in s_df.index: continue

                idx_loc = s_df.index.get_loc(t_ts)
                if idx_loc < 5: continue

                s_close = s_df.iloc[idx_loc]['Close']
                s_close_prev5 = s_df.iloc[idx_loc - 5]['Close']
                s_5d_ret = (s_close - s_close_prev5) / s_close_prev5 * 100.0

                rs = s_5d_ret - nifty_5d_ret

                if rs > 2.0:
                    stock_rs.append({'symbol': symbol, 'rs': rs, 'idx_loc': idx_loc, 's_df': s_df})
            except Exception:
                continue

        if not stock_rs: continue

        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_candidates = stock_rs[:3]

        for cand in top_rs_candidates:
            sym = cand['symbol']
            idx_loc = cand['idx_loc']
            s_df = cand['s_df']

            if idx_loc + 1 >= len(s_df): continue

            next_row = s_df.iloc[idx_loc + 1]
            entry_dt = s_df.index[idx_loc + 1]
            entry = next_row['Open']
            sl = entry * 0.98
            risk_r = entry - sl
            t1 = entry + 1.5 * risk_r
            t2 = entry + 2.5 * risk_r

            pos_size = int((running_capital * 0.01) / risk_r)
            if pos_size <= 0: continue

            future_candles = s_df.iloc[idx_loc + 1 : idx_loc + 6]
            outcome = 'EXPIRED'
            exit_price = future_candles.iloc[-1]['Close']
            trail_sl = sl

            for f_idx, f_row in future_candles.iterrows():
                f_high = f_row['High']
                f_low = f_row['Low']

                if f_high >= (entry + 1.0 * risk_r):
                    trail_sl = max(trail_sl, entry)

                if f_high >= t1:
                    outcome = 'HIT_T1'
                    exit_price = t1
                    if f_high >= t2:
                        outcome = 'HIT_T2'
                        exit_price = t2
                    break
                elif f_low <= trail_sl:
                    outcome = 'HIT_SL' if trail_sl < entry else 'HIT_BE'
                    exit_price = trail_sl
                    break

            pnl = (exit_price - entry) * pos_size
            ret_ratio = pnl / running_capital
            running_capital += pnl

            trigger_dt_str = entry_dt.strftime('%Y-%m-%d 09:15')
            trigger_time_str = '09:15 AM'

            trades.append({
                'Date': str(entry_dt.date()),
                'Trigger_Time': trigger_time_str,
                'Timestamp': trigger_dt_str,
                'Symbol': sym.replace('.NS', ''),
                'Direction': 'LONG',
                'Entry_Price': round(entry, 2),
                'Exit_Price': round(exit_price, 2),
                'SL_Price': round(sl, 2),
                'Shares': pos_size,
                'Outcome': outcome,
                'PnL_Rs': round(pnl, 2),
                'Return_Pct': round(ret_ratio, 6),
                'Capital_After': round(running_capital, 2)
            })

    df_export = pd.DataFrame(trades)
    print(f"Generated ALL {len(df_export)} trades over 3 years.")

    # Export to CSV
    csv_path = "3year_trades_log.csv"
    brain_csv_path = r"C:\Users\ASUS\.gemini\antigravity\brain\3f4a3a4c-9e99-4921-807e-44f24c8fd355\3year_trades_log.csv"
    df_export.to_csv(csv_path, index=False)
    df_export.to_csv(brain_csv_path, index=False)

    # Export to Excel Workbook (.xlsx)
    excel_path = "3year_trades_report.xlsx"
    brain_excel_path = r"C:\Users\ASUS\.gemini\antigravity\brain\3f4a3a4c-9e99-4921-807e-44f24c8fd355\3year_trades_report.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "3-Year Trade Log"

    ws.append(["FULL 3-YEAR HISTORICAL TRADE LOG — NIFTY RELATIVE STRENGTH STRATEGY + REGIME FILTER"])
    ws.append([f"Starting Capital: Rs. 100,000.00 | Ending Capital: Rs. {running_capital:,.2f} | Net Return: +{(running_capital-100000)/1000:.2f}% | Total Trades: {len(df_export)}"])
    ws.append([])

    headers = ["#", "Date", "Trigger Time", "Timestamp", "Symbol", "Direction", "Entry Price (Rs)", "Exit Price (Rs)", "Stop Loss (Rs)", "Shares", "Outcome", "P&L (Rs)", "Return %", "Capital After (Rs)"]
    ws.append(headers)

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    win_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    loss_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    be_fill = PatternFill(start_color="EDEDED", end_color="EDEDED", fill_type="solid")

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for idx, row in df_export.iterrows():
        r_idx = idx + 5
        ws.append([
            idx + 1,
            row['Date'],
            row['Trigger_Time'],
            row['Timestamp'],
            row['Symbol'],
            row['Direction'],
            row['Entry_Price'],
            row['Exit_Price'],
            row['SL_Price'],
            row['Shares'],
            row['Outcome'],
            row['PnL_Rs'],
            row['Return_Pct'],
            row['Capital_After']
        ])

        fill = win_fill if row['Outcome'] in ['HIT_T1', 'HIT_T2'] else (loss_fill if row['Outcome'] == 'HIT_SL' else be_fill)
        for col_num in range(1, 15):
            cell = ws.cell(row=r_idx, column=col_num)
            cell.fill = fill
            if col_num in [7, 8, 9, 12, 14]:
                cell.number_format = '#,##0.00'
            elif col_num == 13:
                cell.number_format = '+0.00%;-0.00%;0.00%'

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    wb.save(excel_path)
    wb.save(brain_excel_path)
    print(f"Exported ALL {len(df_export)} trades to CSV & Excel!")

if __name__ == '__main__':
    export_full_3year_trades()
