"""
Export Clean 3-Year CSV File for Direct Google Sheets Import
"""
import pandas as pd
import openpyxl

def generate_clean_csv_and_xlsx():
    # Convert existing XLSX to clean CSV & verified XLSX
    excel_path = "3year_trades_report.xlsx"
    df = pd.read_excel(excel_path, skiprows=3)

    csv_path = "3year_trades_log.csv"
    brain_csv_path = r"C:\Users\ASUS\.gemini\antigravity\brain\3f4a3a4c-9e99-4921-807e-44f24c8fd355\3year_trades_log.csv"

    df.to_csv(csv_path, index=False)
    df.to_csv(brain_csv_path, index=False)

    print(f"Clean CSV exported to {csv_path} and {brain_csv_path}")

if __name__ == '__main__':
    generate_clean_csv_and_xlsx()
