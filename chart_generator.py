"""
Candlestick Chart Generator with Entry, SL, Target 1, Target 2 Levels overlay.
Uses matplotlib & yfinance to render high-definition dark mode candlestick charts.
"""
import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server/bot
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import yfinance as yf

def generate_candlestick_chart(pick: dict) -> str:
    """
    Generates a dark-mode candlestick chart with Entry, SL, T1, and T2 price levels drawn.
    Returns the file path of the generated PNG chart.
    """
    symbol = pick.get('symbol', 'STOCK')
    ticker = pick.get('ticker', f"{symbol}.NS")
    entry = pick.get('entry', 0.0)
    sl = pick.get('sl', 0.0)
    target1 = pick.get('target1', 0.0)
    target2 = pick.get('target2', 0.0)

    # Fetch 15-day daily candle data for visual context
    try:
        df = yf.download(ticker, period="20d", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close']).tail(15)
    except Exception as e:
        print(f"Error downloading chart data for {symbol}: {e}")
        return ""

    if df.empty:
        return ""

    # Create Dark Mode Plot
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor('#0E1621')
    ax.set_facecolor('#17212B')

    # Draw Candlesticks
    df['DateNum'] = mdates.date2num(df.index)
    width = 0.6

    for i, (dt, row) in enumerate(df.iterrows()):
        color = '#00E676' if row['Close'] >= row['Open'] else '#FF5252'
        # Wick
        ax.plot([i, i], [row['Low'], row['High']], color=color, linewidth=1.2)
        # Body
        body_bottom = min(row['Open'], row['Close'])
        body_height = max(abs(row['Close'] - row['Open']), 0.01)
        rect = plt.Rectangle((i - width/2, body_bottom), width, body_height, facecolor=color, edgecolor=color, alpha=0.9)
        ax.add_patch(rect)

    # X-axis Date Labels
    date_labels = [d.strftime('%d-%b') for d in df.index]
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(date_labels, rotation=45, ha='right', fontsize=9, color='#8E99A2')

    # Add Horizontal Level Lines
    x_min, x_max = -0.5, len(df) - 0.5
    ax.set_xlim(x_min, x_max)

    # Entry Line (Blue)
    ax.hlines(y=entry, xmin=x_min, xmax=x_max, colors='#29B6F6', linestyles='--', linewidth=1.5, label=f'Entry: Rs. {entry:,.2f}')
    # SL Line (Red)
    ax.hlines(y=sl, xmin=x_min, xmax=x_max, colors='#FF1744', linestyles='--', linewidth=1.5, label=f'SL: Rs. {sl:,.2f} (-2.0%)')
    # Target 1 Line (Light Green)
    ax.hlines(y=target1, xmin=x_min, xmax=x_max, colors='#00E676', linestyles='-.', linewidth=1.5, label=f'Target 1: Rs. {target1:,.2f} (+3.0%)')
    # Target 2 Line (Bright Green)
    ax.hlines(y=target2, xmin=x_min, xmax=x_max, colors='#B2FF59', linestyles='-', linewidth=1.8, label=f'Target 2: Rs. {target2:,.2f} (+5.0%)')

    # Titles & Labels
    ax.set_title(f"🚀 INTRADAY BREAKOUT SETUP: {symbol} (LONG)", fontsize=14, fontweight='bold', color='#FFFFFF', pad=15)
    ax.set_ylabel("Price (Rs.)", fontsize=10, color='#8E99A2')
    ax.grid(True, linestyle=':', alpha=0.2, color='#FFFFFF')

    # Price Level Callout Annotations on Right Edge
    right_x = len(df) - 0.2
    ax.annotate(f"  T2: Rs. {target2:,.2f}", xy=(right_x, target2), fontsize=9, fontweight='bold', color='#B2FF59', verticalalignment='center')
    ax.annotate(f"  T1: Rs. {target1:,.2f}", xy=(right_x, target1), fontsize=9, fontweight='bold', color='#00E676', verticalalignment='center')
    ax.annotate(f"  ENTRY: Rs. {entry:,.2f}", xy=(right_x, entry), fontsize=9, fontweight='bold', color='#29B6F6', verticalalignment='center')
    ax.annotate(f"  SL: Rs. {sl:,.2f}", xy=(right_x, sl), fontsize=9, fontweight='bold', color='#FF1744', verticalalignment='center')

    ax.legend(loc='upper left', frameon=True, facecolor='#17212B', edgecolor='#2B5278', fontsize=9)

    plt.tight_layout()

    # Save to disk
    os.makedirs('charts', exist_ok=True)
    chart_file = os.path.join('charts', f"chart_{symbol}.png")
    plt.savefig(chart_file, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close()

    print(f"Chart generated successfully: {chart_file}")
    return chart_file

if __name__ == '__main__':
    sample_pick = {
        'symbol': 'BDL',
        'entry': 1281.80,
        'sl': 1256.16,
        'target1': 1320.25,
        'target2': 1345.89
    }
    generate_candlestick_chart(sample_pick)
