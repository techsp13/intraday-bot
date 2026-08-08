"""
Update create_markdown_table.py with corrected Return % formatting
"""
import pandas as pd

def convert_csv_to_md_table():
    df = pd.read_csv("1year_trades_log.csv")

    md_content = """# 📊 Complete 1-Year Trade Log (Formatted Table)

### Strategy: NIFTY Relative Strength (RS) Momentum + Market Regime Filter
**Starting Capital**: Rs. 100,000.00 | **Ending Capital**: Rs. 119,972.71 | **Net Return**: **+19.97%**

---

| # | Date | Symbol | Direction | Entry Price (Rs.) | Exit Price (Rs.) | SL Price (Rs.) | Shares | Outcome | P&L (Rs.) | Return (%) | Capital After (Rs.) |
|---|---|---|---|---|---|---|---|---|---|---|---|
"""

    for idx, row in df.iterrows():
        outcome_emoji = "🟢" if row['Outcome'] in ['HIT_T1', 'HIT_T2'] else ("🔴" if row['Outcome'] == 'HIT_SL' else "⚪")
        pnl_str = f"+Rs. {row['PnL_Rs']:,.2f}" if row['PnL_Rs'] > 0 else f"-Rs. {abs(row['PnL_Rs']):,.2f}"
        ret_val = row['Return_Pct'] * 100.0
        ret_str = f"+{ret_val:.2f}%" if ret_val > 0 else f"{ret_val:.2f}%"

        md_content += f"| {idx+1} | {row['Date']} | **{row['Symbol']}** | {row['Direction']} | {row['Entry_Price']:,.2f} | {row['Exit_Price']:,.2f} | {row['SL_Price']:,.2f} | {row['Shares']} | {outcome_emoji} {row['Outcome']} | `{pnl_str}` | {ret_str} | Rs. {row['Capital_After']:,.2f} |\n"

    target_md_path = r"C:\Users\ASUS\.gemini\antigravity\brain\3f4a3a4c-9e99-4921-807e-44f24c8fd355\1year_trades_summary_table.md"
    with open(target_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Markdown table updated at {target_md_path}")

if __name__ == '__main__':
    convert_csv_to_md_table()
