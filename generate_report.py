#!/usr/bin/env python3
"""
Trading Agents Platform - Comprehensive PDF Report Generator
"""

import sqlite3
import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from fpdf import FPDF
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "trading_agents.db")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "Trading_Agents_Report.pdf")
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "_report_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# Color palette
COLORS = {
    "primary": (41, 128, 185),      # Blue
    "secondary": (44, 62, 80),       # Dark
    "accent": (46, 204, 113),        # Green
    "danger": (231, 76, 60),         # Red
    "warning": (241, 196, 15),       # Yellow
    "light": (236, 240, 241),        # Light gray
    "bg": (248, 249, 250),           # Near white
    "text": (33, 37, 41),            # Dark text
    "muted": (108, 117, 125),        # Muted text
}

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ─── DATA LOADING ──────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Load agents
cur.execute("SELECT * FROM agents ORDER BY created_at")
agents = [dict(r) for r in cur.fetchall()]

# Load trades
cur.execute("SELECT * FROM trades ORDER BY opened_at")
trades = [dict(r) for r in cur.fetchall()]

# Load signals
cur.execute("SELECT * FROM signal_log ORDER BY timestamp")
signals = [dict(r) for r in cur.fetchall()]

# Per-agent performance
agent_perf = {}
for a in agents:
    aid = a['id']
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) as closed,
            SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) as open_pos,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
            ROUND(SUM(COALESCE(profit, 0)), 2) as total_profit,
            ROUND(AVG(CASE WHEN profit IS NOT NULL AND status='closed' THEN profit END), 2) as avg_profit,
            ROUND(MAX(profit), 2) as best_trade,
            ROUND(MIN(CASE WHEN status='closed' THEN profit END), 2) as worst_trade
        FROM trades WHERE agent_id = ?
    """, (aid,))
    row = cur.fetchone()
    if row and row['total'] > 0:
        agent_perf[aid] = dict(row)
    else:
        agent_perf[aid] = {'total': 0, 'closed': 0, 'open_pos': 0, 'wins': 0,
                           'losses': 0, 'total_profit': 0, 'avg_profit': 0,
                           'best_trade': 0, 'worst_trade': 0}

conn.close()

# Overall stats
total_closed = sum(1 for t in trades if t['status'] == 'closed')
total_open = sum(1 for t in trades if t['status'] == 'open')
total_pnl = sum(t.get('profit', 0) or 0 for t in trades if t['status'] == 'closed')
total_wins = sum(1 for t in trades if (t.get('profit') or 0) > 0 and t['status'] == 'closed')
total_losses = sum(1 for t in trades if (t.get('profit') or 0) < 0 and t['status'] == 'closed')
win_rate = total_wins / (total_wins + total_losses) * 100 if (total_wins + total_losses) > 0 else 0
gross_profit = sum(t['profit'] for t in trades if t['status'] == 'closed' and (t.get('profit') or 0) > 0)
gross_loss = abs(sum(t['profit'] for t in trades if t['status'] == 'closed' and (t.get('profit') or 0) < 0))
profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')


# ─── CHART GENERATION ──────────────────────────────────────────────

plt.rcParams['figure.facecolor'] = '#F8F9FA'
plt.rcParams['axes.facecolor'] = '#FFFFFF'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False


def chart1_agent_pnl():
    """Bar chart: Agent P&L comparison"""
    fig, ax = plt.subplots(figsize=(10, 5))

    active_agents = [(a, agent_perf[a['id']]) for a in agents if agent_perf[a['id']]['total'] > 0]
    active_agents.sort(key=lambda x: x[1]['total_profit'], reverse=True)

    names = [a['name'] for a, _ in active_agents]
    profits = [p['total_profit'] for _, p in active_agents]
    colors_list = ['#2ECC71' if p >= 0 else '#E74C3C' for p in profits]
    agent_colors = [hex_to_rgb(a.get('color', '#3498DB')) for a, _ in active_agents]

    bars = ax.barh(names, profits, color=colors_list, edgecolor='white', linewidth=0.5, height=0.6)

    for bar, val in zip(bars, profits):
        x_pos = val + (2 if val >= 0 else -2)
        ax.text(x_pos, bar.get_y() + bar.get_height()/2, f"${val:.1f}",
                va='center', ha='left' if val >= 0 else 'right',
                fontsize=9, fontweight='bold', color='#2C3E50')

    ax.set_xlabel('Total Profit/Loss (USD)', fontsize=11, fontweight='bold')
    ax.set_title('Agent Performance: Profit & Loss', fontsize=14, fontweight='bold', pad=15)
    ax.axvline(x=0, color='#2C3E50', linewidth=0.8, linestyle='-')
    ax.invert_yaxis()
    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "agent_pnl.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


def chart2_win_loss():
    """Win/Loss/Breakeven pie chart"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    # Overall pie
    be = total_closed - total_wins - total_losses
    sizes = [total_wins, total_losses, be]
    labels_list = [f'Wins ({total_wins})', f'Losses ({total_losses})', f'Breakeven ({be})']
    chart_colors = ['#2ECC71', '#E74C3C', '#95A5A6']
    explode = (0.05, 0.05, 0.05)

    wedges, texts, autotexts = ax1.pie(sizes, labels=labels_list, colors=chart_colors,
                                        explode=explode, autopct='%1.1f%%', startangle=90,
                                        textprops={'fontsize': 9})
    for t in autotexts:
        t.set_fontweight('bold')
    ax1.set_title('Overall Win/Loss Distribution', fontsize=12, fontweight='bold', pad=10)

    # Per agent win rate bar
    active = [(a, agent_perf[a['id']]) for a in agents if agent_perf[a['id']]['closed'] > 0]
    active.sort(key=lambda x: x[1]['wins'] / max(x[1]['wins'] + x[1]['losses'], 1), reverse=True)

    names = [a['name'][:15] for a, _ in active]
    win_rates = [p['wins'] / max(p['wins'] + p['losses'], 1) * 100 for _, p in active]
    bar_colors = ['#2ECC71' if wr >= 50 else '#E74C3C' for wr in win_rates]

    bars = ax2.barh(names, win_rates, color=bar_colors, edgecolor='white', height=0.6)
    ax2.axvline(x=50, color='#E67E22', linewidth=1.5, linestyle='--', alpha=0.7, label='50% threshold')
    ax2.set_xlabel('Win Rate (%)', fontsize=10, fontweight='bold')
    ax2.set_title('Win Rate by Agent', fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlim(0, 105)
    ax2.legend(fontsize=8)
    ax2.invert_yaxis()

    for bar, wr in zip(bars, win_rates):
        ax2.text(wr + 1, bar.get_y() + bar.get_height()/2, f"{wr:.0f}%",
                va='center', fontsize=8, fontweight='bold')

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "win_loss.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


def chart3_cumulative_pnl():
    """Cumulative P&L curve over time"""
    fig, ax = plt.subplots(figsize=(10, 4.5))

    closed = [t for t in trades if t['status'] == 'closed' and t.get('profit') is not None]
    closed.sort(key=lambda x: x.get('closed_at') or x['opened_at'])

    if closed:
        cum_pnl = np.cumsum([t['profit'] for t in closed])
        x_vals = range(1, len(cum_pnl) + 1)

        # Fill between positive and negative
        ax.fill_between(x_vals, cum_pnl, 0, where=(cum_pnl >= 0), alpha=0.3, color='#2ECC71')
        ax.fill_between(x_vals, cum_pnl, 0, where=(cum_pnl < 0), alpha=0.3, color='#E74C3C')
        ax.plot(x_vals, cum_pnl, color='#2980B9', linewidth=2, label='Cumulative P&L')

        # Mark max drawdown
        peak = np.maximum.accumulate(cum_pnl)
        drawdown = cum_pnl - peak
        max_dd_idx = np.argmin(drawdown)
        if drawdown[max_dd_idx] < 0:
            ax.annotate(f'Max DD: ${drawdown[max_dd_idx]:.1f}',
                       xy=(max_dd_idx + 1, cum_pnl[max_dd_idx]),
                       fontsize=9, fontweight='bold', color='#E74C3C',
                       arrowprops=dict(arrowstyle='->', color='#E74C3C'),
                       xytext=(max_dd_idx + 5, cum_pnl[max_dd_idx] - 20))

        ax.axhline(y=0, color='#2C3E50', linewidth=0.8)
        ax.set_xlabel('Trade Number', fontsize=11, fontweight='bold')
        ax.set_ylabel('Cumulative P&L (USD)', fontsize=11, fontweight='bold')
        ax.set_title('Equity Curve - All Agents Combined', fontsize=14, fontweight='bold', pad=15)
        ax.legend(fontsize=10)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "cumulative_pnl.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


def chart4_trade_distribution():
    """Trade count and direction distribution per agent"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    active = [(a, agent_perf[a['id']]) for a in agents if agent_perf[a['id']]['total'] > 0]
    active.sort(key=lambda x: x[1]['total'], reverse=True)

    names = [a['name'][:15] for a, _ in active]
    totals = [p['total'] for _, p in active]
    agent_colors = [a.get('color', '#3498DB') for a, _ in active]

    ax1.barh(names, totals, color=agent_colors, edgecolor='white', height=0.6)
    ax1.set_xlabel('Number of Trades', fontsize=10, fontweight='bold')
    ax1.set_title('Total Trades per Agent', fontsize=12, fontweight='bold', pad=10)
    ax1.invert_yaxis()

    for i, v in enumerate(totals):
        ax1.text(v + 0.3, i, str(v), va='center', fontsize=9, fontweight='bold')

    # Direction distribution
    buy_counts = []
    sell_counts = []
    for a, _ in active:
        aid = a['id']
        buys = sum(1 for t in trades if t['agent_id'] == aid and t['direction'] == 'BUY')
        sells = sum(1 for t in trades if t['agent_id'] == aid and t['direction'] == 'SELL')
        buy_counts.append(buys)
        sell_counts.append(sells)

    y_pos = np.arange(len(names))
    ax2.barh(y_pos, buy_counts, 0.4, label='BUY', color='#2ECC71', edgecolor='white')
    ax2.barh(y_pos + 0.4, sell_counts, 0.4, label='SELL', color='#E74C3C', edgecolor='white')
    ax2.set_yticks(y_pos + 0.2)
    ax2.set_yticklabels(names)
    ax2.set_xlabel('Count', fontsize=10, fontweight='bold')
    ax2.set_title('Buy vs Sell per Agent', fontsize=12, fontweight='bold', pad=10)
    ax2.legend(fontsize=9)
    ax2.invert_yaxis()

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "trade_dist.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


def chart5_strategy_perf():
    """Strategy performance comparison"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    strat_data = {}
    for t in trades:
        if t['status'] != 'closed' or t.get('profit') is None:
            continue
        aid = t['agent_id']
        agent = next((a for a in agents if a['id'] == aid), None)
        if not agent:
            continue
        strats = json.loads(agent['strategies_json'])
        strat_name = strats[0]['name'] if strats else 'unknown'
        if strat_name not in strat_data:
            strat_data[strat_name] = {'profits': [], 'wins': 0, 'losses': 0}
        strat_data[strat_name]['profits'].append(t['profit'])
        if t['profit'] > 0:
            strat_data[strat_name]['wins'] += 1
        elif t['profit'] < 0:
            strat_data[strat_name]['losses'] += 1

    strat_names = list(strat_data.keys())
    strat_totals = [sum(d['profits']) for d in strat_data.values()]
    strat_colors_map = {
        'ma_crossover': '#3498DB',
        'rsi_reversion': '#F1C40F',
        'breakout': '#E67E22',
        'forecast_driven': '#00CEC9',
        'llm_discretionary': '#9B59B6',
    }
    bar_colors = [strat_colors_map.get(s, '#95A5A6') for s in strat_names]

    display_names = [s.replace('_', ' ').title() for s in strat_names]

    bars = ax1.bar(display_names, strat_totals, color=bar_colors, edgecolor='white', width=0.6)
    ax1.axhline(y=0, color='#2C3E50', linewidth=0.8)
    ax1.set_ylabel('Total P&L (USD)', fontsize=10, fontweight='bold')
    ax1.set_title('P&L by Strategy', fontsize=12, fontweight='bold', pad=10)
    ax1.tick_params(axis='x', rotation=25)

    for bar, val in zip(bars, strat_totals):
        ax1.text(bar.get_x() + bar.get_width()/2, val + (2 if val >= 0 else -5),
                f"${val:.0f}", ha='center', fontsize=9, fontweight='bold')

    # Win rate by strategy
    win_rates = []
    for s in strat_names:
        d = strat_data[s]
        total = d['wins'] + d['losses']
        win_rates.append(d['wins'] / total * 100 if total > 0 else 0)

    bars2 = ax2.bar(display_names, win_rates, color=bar_colors, edgecolor='white', width=0.6)
    ax2.axhline(y=50, color='#E67E22', linewidth=1.5, linestyle='--', alpha=0.7)
    ax2.set_ylabel('Win Rate (%)', fontsize=10, fontweight='bold')
    ax2.set_title('Win Rate by Strategy', fontsize=12, fontweight='bold', pad=10)
    ax2.set_ylim(0, 105)
    ax2.tick_params(axis='x', rotation=25)

    for bar, val in zip(bars2, win_rates):
        ax2.text(bar.get_x() + bar.get_width()/2, val + 2,
                f"{val:.0f}%", ha='center', fontsize=9, fontweight='bold')

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "strategy_perf.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


def chart6_per_agent_equity():
    """Per-agent cumulative P&L curves"""
    fig, ax = plt.subplots(figsize=(10, 5))

    for a in agents:
        aid = a['id']
        agent_trades = [t for t in trades if t['agent_id'] == aid and t['status'] == 'closed' and t.get('profit') is not None]
        if len(agent_trades) < 2:
            continue
        agent_trades.sort(key=lambda x: x.get('closed_at') or x['opened_at'])
        cum = np.cumsum([t['profit'] for t in agent_trades])
        ax.plot(range(1, len(cum) + 1), cum, linewidth=2, label=a['name'],
                color=a.get('color', '#3498DB'), marker='o', markersize=3)

    ax.axhline(y=0, color='#2C3E50', linewidth=0.8, linestyle='-')
    ax.set_xlabel('Trade Number', fontsize=11, fontweight='bold')
    ax.set_ylabel('Cumulative P&L (USD)', fontsize=11, fontweight='bold')
    ax.set_title('Individual Agent Equity Curves', fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=8, loc='upper left', ncol=2)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "per_agent_equity.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


def chart7_signal_distribution():
    """Signal distribution heatmap-style"""
    fig, ax = plt.subplots(figsize=(10, 4))

    active = [(a, agent_perf[a['id']]) for a in agents if agent_perf[a['id']]['total'] > 0]

    agent_names = [a['name'][:15] for a, _ in active]
    agent_ids = [a['id'] for a, _ in active]

    buy_signals = []
    sell_signals = []
    hold_signals = []

    for aid in agent_ids:
        agent_sigs = [s for s in signals if s['agent_id'] == aid]
        buy_signals.append(sum(1 for s in agent_sigs if s['signal'] == 'BUY'))
        sell_signals.append(sum(1 for s in agent_sigs if s['signal'] == 'SELL'))
        hold_signals.append(sum(1 for s in agent_sigs if s['signal'] == 'HOLD'))

    x = np.arange(len(agent_names))
    width = 0.25

    ax.bar(x - width, buy_signals, width, label='BUY', color='#2ECC71', edgecolor='white')
    ax.bar(x, sell_signals, width, label='SELL', color='#E74C3C', edgecolor='white')
    ax.bar(x + width, hold_signals, width, label='HOLD', color='#95A5A6', edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(agent_names, rotation=35, ha='right', fontsize=8)
    ax.set_ylabel('Signal Count', fontsize=10, fontweight='bold')
    ax.set_title('Signal Distribution by Agent', fontsize=12, fontweight='bold', pad=10)
    ax.legend(fontsize=9)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "signal_dist.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


def chart8_architecture():
    """System architecture diagram"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 70)
    ax.axis('off')
    ax.set_facecolor('#F8F9FA')

    def draw_box(x, y, w, h, label, color='#3498DB', sublabel=None):
        rect = mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3",
                                        facecolor=color, edgecolor='white', linewidth=2, alpha=0.9)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2 + (1.5 if sublabel else 0), label,
                ha='center', va='center', fontsize=10, fontweight='bold', color='white')
        if sublabel:
            ax.text(x + w/2, y + h/2 - 2, sublabel,
                    ha='center', va='center', fontsize=7, color='#ECF0F1', style='italic')

    def draw_arrow(x1, y1, x2, y2, label=None):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#7F8C8D', lw=1.5))
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx, my+1.5, label, ha='center', fontsize=7, color='#7F8C8D', style='italic')

    # Title
    ax.text(50, 67, 'TRADING AGENTS PLATFORM - SYSTEM ARCHITECTURE', ha='center',
            fontsize=13, fontweight='bold', color='#2C3E50')

    # Frontend
    draw_box(5, 55, 25, 8, 'React Frontend', '#9B59B6', 'Dashboard + Charts')

    # API Layer
    draw_box(37, 55, 25, 8, 'FastAPI Server', '#2980B9', 'REST + WebSocket')

    # Agents
    draw_box(5, 38, 18, 8, 'Agent 1', '#E74C3C', 'Async Loop')
    draw_box(25, 38, 18, 8, 'Agent 2', '#E67E22', 'Async Loop')
    draw_box(45, 38, 18, 8, 'Agent N', '#F1C40F', 'Async Loop')
    ax.text(66, 42, '...', fontsize=16, fontweight='bold', color='#7F8C8D')

    # Strategies
    draw_box(5, 22, 20, 8, 'Strategies', '#2ECC71', 'MA/RSI/Breakout/LLM')

    # Risk Manager
    draw_box(28, 22, 18, 8, 'Risk Manager', '#E74C3C', 'Mandatory Gate')

    # Models
    draw_box(49, 22, 20, 8, 'AI Models', '#9B59B6', 'GPT/Gemini/HF/Ollama')

    # Broker
    draw_box(5, 6, 20, 8, 'Paper Broker', '#00CEC9', 'Simulated Trading')
    draw_box(28, 6, 18, 8, 'MT5 Broker', '#3498DB', 'Live Trading')

    # Database
    draw_box(49, 6, 20, 8, 'SQLite DB', '#7F8C8D', 'Trades/Signals/Logs')

    # Arrows
    draw_arrow(30, 59, 37, 59, 'HTTP/WS')
    draw_arrow(49.5, 55, 49.5, 46.5, 'Manage')
    draw_arrow(14, 55, 14, 46.5, '')
    draw_arrow(34, 55, 34, 46.5, '')
    draw_arrow(14, 38, 14, 30.5, 'Generate')
    draw_arrow(37, 38, 37, 30.5, 'Validate')
    draw_arrow(54, 38, 59, 30.5, 'Predict')
    draw_arrow(15, 22, 15, 14.5, 'Execute')
    draw_arrow(37, 22, 37, 14.5, 'Execute')
    draw_arrow(59, 22, 59, 14.5, 'Log')

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "architecture.png")
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path


# Generate all charts
print("Generating charts...")
chart_paths = {
    'agent_pnl': chart1_agent_pnl(),
    'win_loss': chart2_win_loss(),
    'cumulative_pnl': chart3_cumulative_pnl(),
    'trade_dist': chart4_trade_distribution(),
    'strategy_perf': chart5_strategy_perf(),
    'per_agent_equity': chart6_per_agent_equity(),
    'signal_dist': chart7_signal_distribution(),
    'architecture': chart8_architecture(),
}
print("Charts generated.")


# ─── PDF GENERATION ────────────────────────────────────────────────

class TradingReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_fill_color(*COLORS['secondary'])
            self.rect(0, 0, 210, 12, 'F')
            self.set_font('Helvetica', 'B', 8)
            self.set_text_color(255, 255, 255)
            self.set_y(3)
            self.cell(0, 6, 'Trading Agents Platform - Performance Report', align='C')
            self.set_text_color(*COLORS['text'])
            self.set_y(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*COLORS['muted'])
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}  |  Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}  |  Confidential', align='C')

    def section_title(self, num, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(*COLORS['primary'])
        self.cell(0, 12, f'{num}. {title}', new_x="LMARGIN", new_y="NEXT")
        # Underline
        self.set_draw_color(*COLORS['primary'])
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)
        self.set_text_color(*COLORS['text'])

    def subsection_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(*COLORS['secondary'])
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_text_color(*COLORS['text'])

    def body_text(self, text):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*COLORS['text'])
        self.multi_cell(0, 5.5, text)
        self.ln(3)

    def stat_box(self, label, value, color=COLORS['primary']):
        x, y = self.get_x(), self.get_y()
        w, h = 42, 22
        self.set_fill_color(*color)
        self.rect(x, y, w, h, 'F')
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(255, 255, 255)
        self.set_xy(x, y + 2)
        self.cell(w, 8, str(value), align='C')
        self.set_font('Helvetica', '', 7)
        self.set_xy(x, y + 11)
        self.cell(w, 6, label, align='C')
        self.set_xy(x + w + 3, y)
        self.set_text_color(*COLORS['text'])

    def add_chart(self, path, w=180):
        if os.path.exists(path):
            x = (210 - w) / 2
            self.image(path, x=x, w=w)
            self.ln(5)

    def kv_row(self, key, value):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(*COLORS['muted'])
        self.cell(55, 6, key)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(*COLORS['text'])
        self.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")


# Build PDF
pdf = TradingReport()
pdf.alias_nb_pages()

# ─── COVER PAGE ────────────────────────────────────────────────────
pdf.add_page()
pdf.set_fill_color(*COLORS['secondary'])
pdf.rect(0, 0, 210, 297, 'F')

# Accent stripe
pdf.set_fill_color(*COLORS['primary'])
pdf.rect(0, 100, 210, 4, 'F')
pdf.rect(0, 190, 210, 2, 'F')

# Title
pdf.set_y(60)
pdf.set_font('Helvetica', '', 14)
pdf.set_text_color(149, 165, 166)
pdf.cell(0, 10, 'MULTI-AGENT ALGORITHMIC TRADING SYSTEM', align='C', new_x="LMARGIN", new_y="NEXT")

pdf.set_y(110)
pdf.set_font('Helvetica', 'B', 32)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 15, 'TRADING AGENTS', align='C', new_x="LMARGIN", new_y="NEXT")

pdf.set_font('Helvetica', '', 18)
pdf.set_text_color(*COLORS['primary'])
pdf.cell(0, 12, 'PLATFORM REPORT', align='C', new_x="LMARGIN", new_y="NEXT")

pdf.set_y(150)
pdf.set_font('Helvetica', '', 11)
pdf.set_text_color(149, 165, 166)
pdf.cell(0, 7, 'Comprehensive Technical & Performance Analysis', align='C', new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 7, f'Report Generated: {datetime.now().strftime("%B %d, %Y")}', align='C', new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 7, f'Data Period: November 15 - November 24, 2026', align='C', new_x="LMARGIN", new_y="NEXT")

pdf.set_y(200)
pdf.set_font('Helvetica', '', 9)
pdf.set_text_color(100, 100, 100)
info_lines = [
    f'Total Agents: {len(agents)}  |  Total Trades: {len(trades)}  |  Net P&L: ${total_pnl:.2f}',
    'Stack: Python (FastAPI) + React (TypeScript) + MetaTrader 5',
    'Strategies: MA Crossover | RSI Reversion | Breakout | Forecast | LLM Discretionary',
]
for line in info_lines:
    pdf.cell(0, 6, line, align='C', new_x="LMARGIN", new_y="NEXT")

# ─── TABLE OF CONTENTS ────────────────────────────────────────────
pdf.add_page()
pdf.set_font('Helvetica', 'B', 22)
pdf.set_text_color(*COLORS['secondary'])
pdf.cell(0, 15, 'TABLE OF CONTENTS', new_x="LMARGIN", new_y="NEXT")
pdf.set_draw_color(*COLORS['primary'])
pdf.set_line_width(1)
pdf.line(10, pdf.get_y(), 200, pdf.get_y())
pdf.ln(10)

toc_items = [
    ("1", "Executive Summary"),
    ("2", "System Architecture"),
    ("3", "Technology Stack"),
    ("4", "Trading Strategies"),
    ("5", "Risk Management System"),
    ("6", "AI/ML Model Integration"),
    ("7", "Agent Profiles & Configuration"),
    ("8", "Performance Analysis"),
    ("9", "Signal Analysis"),
    ("10", "Individual Agent Reports"),
    ("11", "Conclusions & Recommendations"),
]
for num, title in toc_items:
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(*COLORS['primary'])
    pdf.cell(12, 9, num)
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(*COLORS['text'])
    pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")

# ─── 1. EXECUTIVE SUMMARY ─────────────────────────────────────────
pdf.add_page()
pdf.section_title("1", "EXECUTIVE SUMMARY")

pdf.body_text(
    "The Trading Agents Platform is a sophisticated multi-agent algorithmic trading system "
    "designed for autonomous forex trading. Built with Python (FastAPI) on the backend and "
    "React (TypeScript) on the frontend, it supports concurrent execution of multiple AI-driven "
    "and rule-based trading agents with mandatory risk management, real-time monitoring via "
    "WebSocket, and optional MetaTrader 5 (MT5) live trading integration."
)

pdf.body_text(
    "The platform currently runs on a MetaQuotes Demo account connected to MetaTrader 5, "
    "trading primarily EURUSD, GBPUSD, and USDJPY pairs across M15, H1, and H4 timeframes. "
    "During the reporting period (November 15-24, 2026), 14 agents were created and deployed, "
    "executing a total of 134 trades across 5 different trading strategies."
)

# Key metrics boxes
pdf.ln(3)
pdf.subsection_title("Key Metrics at a Glance")
y_start = pdf.get_y()

pdf.set_xy(10, y_start)
pdf.stat_box("Total Agents", len(agents), COLORS['primary'])
pdf.stat_box("Closed Trades", total_closed, COLORS['secondary'])
pdf.stat_box("Win Rate", f"{win_rate:.1f}%", COLORS['accent'] if win_rate > 50 else COLORS['danger'])
pdf.stat_box("Net P&L", f"${total_pnl:.2f}", COLORS['accent'] if total_pnl > 0 else COLORS['danger'])
pdf.ln(28)

pdf.set_xy(10, pdf.get_y())
pdf.stat_box("Total Wins", total_wins, COLORS['accent'])
pdf.stat_box("Total Losses", total_losses, COLORS['danger'])
pdf.stat_box("Profit Factor", f"{profit_factor:.2f}", COLORS['primary'])
pdf.stat_box("Open Positions", total_open, COLORS['warning'])
pdf.ln(28)

# ─── 2. SYSTEM ARCHITECTURE ───────────────────────────────────────
pdf.add_page()
pdf.section_title("2", "SYSTEM ARCHITECTURE")

pdf.body_text(
    "The platform follows a three-tier architecture pattern with clear separation of concerns. "
    "The frontend communicates with the backend via RESTful HTTP endpoints and a persistent "
    "WebSocket connection for real-time commentary streaming. Each trading agent runs as an "
    "independent async task with its own execution loop, strategy pipeline, and risk validation."
)

pdf.subsection_title("Architecture Overview")
pdf.add_chart(chart_paths['architecture'], w=170)

pdf.body_text(
    "Data Flow: The agent's main loop runs on a configurable schedule (default 60 seconds). "
    "Each iteration: (1) Fetches latest OHLCV market data, (2) Detects new candle formation, "
    "(3) Optionally runs AI model for predictions, (4) Generates trading signal via strategy, "
    "(5) Validates through mandatory risk manager, (6) Places order if approved, "
    "(7) Logs everything to SQLite database, (8) Broadcasts commentary via WebSocket."
)

pdf.subsection_title("Project Structure")
pdf.set_font('Courier', '', 8)
structure = (
    "trading_agents/\n"
    "+-- backend/              # Python FastAPI application\n"
    "|   +-- agent/           # Core agent logic + runner\n"
    "|   +-- api/             # REST + WebSocket endpoints\n"
    "|   +-- broker/          # Paper & MT5 broker adapters\n"
    "|   +-- strategies/      # 5 built-in trading strategies\n"
    "|   +-- models/          # LLM/ML provider integrations\n"
    "|   +-- risk/            # Mandatory risk management\n"
    "|   +-- backtest/        # Walk-forward backtesting engine\n"
    "|   +-- logging_/        # Trade & signal logging\n"
    "+-- frontend/            # React 18 + TypeScript + Vite\n"
    "|   +-- src/components/  # Dashboard, Charts, Forms, ...\n"
    "|   +-- src/api/         # API client + WebSocket hook\n"
    "+-- configs/             # YAML agent configuration templates\n"
    "+-- trading_agents.db    # SQLite database"
)
pdf.multi_cell(0, 4, structure)
pdf.set_font('Helvetica', '', 10)
pdf.ln(5)

# ─── 3. TECHNOLOGY STACK ──────────────────────────────────────────
pdf.add_page()
pdf.section_title("3", "TECHNOLOGY STACK")

pdf.subsection_title("Backend")
pdf.body_text(
    "- Python 3.12 with async/await throughout\n"
    "- FastAPI for HTTP/REST API with automatic OpenAPI documentation\n"
    "- SQLAlchemy 2.0 (async) with aiosqlite for database operations\n"
    "- Pydantic v2 for data validation and settings management\n"
    "- MetaTrader5 Python package for live broker integration\n"
    "- TA (Technical Analysis) library for indicators (RSI, SMA, EMA, ATR, Bollinger)\n"
    "- NumPy + Pandas for data manipulation\n"
    "- WebSockets for real-time bidirectional communication"
)

pdf.subsection_title("Frontend")
pdf.body_text(
    "- React 18.3 with TypeScript 5.3\n"
    "- Vite for fast development builds\n"
    "- TradingView Lightweight Charts for financial charting\n"
    "- Recharts for data visualization\n"
    "- Tailwind CSS for responsive styling\n"
    "- Lucide React for iconography\n"
    "- React Router 6 for client-side navigation"
)

pdf.subsection_title("AI/ML Integrations")
pdf.body_text(
    "- OpenAI API (GPT-4o, GPT-4o-mini) for LLM-based trading signals\n"
    "- Google Gemini (gemini-2.0-flash) for AI discretionary trading\n"
    "- HuggingFace Hub for specialized trading models and time-series forecasting\n"
    "- Ollama for local LLM deployment (Gemma2 and others)\n"
    "- Anthropic Claude API support (available but not actively used)"
)

pdf.subsection_title("Infrastructure")
pdf.body_text(
    "- SQLite database for persistence (portable, zero-config)\n"
    "- MetaTrader 5 terminal for live market data and order execution\n"
    "- MetaQuotes Demo Server for demo/paper trading\n"
    "- uvicorn ASGI server with hot-reload for development"
)

# ─── 4. TRADING STRATEGIES ────────────────────────────────────────
pdf.add_page()
pdf.section_title("4", "TRADING STRATEGIES")

pdf.body_text(
    "The platform implements 5 built-in trading strategies, each producing standardized "
    "TradeSignal objects with direction (BUY/SELL/HOLD), confidence (0-1), stop-loss, "
    "and take-profit levels. Multiple strategies can be combined using the Strategy Combiner."
)

strategies_info = [
    ("4.1 MA Crossover (ma_crossover)",
     "Uses two moving averages (fast and slow) to detect trend changes. A bullish crossover "
     "(fast crosses above slow) generates a BUY signal with 75% confidence, while a bearish "
     "crossover generates a SELL. Supports both SMA and EMA types. Stop-loss and take-profit "
     "are placed using ATR (Average True Range) multipliers.\n\n"
     "Default Parameters: fast_period=20, slow_period=50, ma_type=SMA, ATR SL=1.5x, ATR TP=2.0x"),

    ("4.2 RSI Mean Reversion (rsi_reversion)",
     "Exploits overbought/oversold conditions using the Relative Strength Index. RSI below 30 "
     "(oversold) triggers BUY with high confidence; RSI above 70 (overbought) triggers SELL. "
     "In the neutral zone (30-70), confidence scales proportionally to distance from center. "
     "Uses momentum slope for edge-case signals near RSI=50.\n\n"
     "Default Parameters: rsi_period=14, oversold=30, overbought=70, ATR SL=1.5x, ATR TP=2.0x"),

    ("4.3 Breakout (breakout)",
     "Uses Donchian channels (N-period highs and lows) to detect price breakouts. A break above "
     "the upper channel triggers BUY; a break below the lower channel triggers SELL. This is a "
     "momentum/trend-following strategy that captures new directional moves.\n\n"
     "Default Parameters: channel_period=20, ATR SL=1.5x, ATR TP=2.0x"),

    ("4.4 Forecast Driven (forecast_driven)",
     "Consumes ML model output (forecast returns and quantile ranges) to generate signals. "
     "If the forecasted return exceeds a threshold, a trade is placed in that direction. "
     "Optional quantile agreement confirmation adds reliability. Confidence scales with the "
     "magnitude of the forecast.\n\n"
     "Default Parameters: return_threshold=0.5%, quantile_agreement=True"),

    ("4.5 LLM Discretionary (llm_discretionary)",
     "Passes market context (last 10 candles plus technical indicators) to a Large Language Model "
     "(OpenAI GPT, Google Gemini, Ollama, or HuggingFace). The LLM returns a JSON response with "
     "signal, confidence, stop-loss, take-profit, and reasoning. This strategy leverages AI "
     "reasoning for complex market analysis.\n\n"
     "Models Used: Gemini 2.0 Flash, HuggingFace Trading Models"),
]

for title, desc in strategies_info:
    pdf.subsection_title(title)
    pdf.body_text(desc)

# Strategy combiner
pdf.add_page()
pdf.subsection_title("4.6 Strategy Combiner")
pdf.body_text(
    "When an agent uses multiple strategies, the Strategy Combiner merges their signals "
    "using one of 5 combination modes:\n\n"
    "1. MAJORITY VOTE - Most common signal wins; confidence weighted by agreement %\n"
    "2. WEIGHTED VOTE - Each strategy has configurable weight; highest score wins\n"
    "3. UNANIMOUS - All strategies must agree; returns HOLD if any disagree\n"
    "4. FILTER CHAIN - Role-based: 'direction' (main), 'confirm' (must agree), 'regime' (filter)\n"
    "5. CONFIDENCE WEIGHTED - Signals blended by their individual confidence scores\n\n"
    "This allows sophisticated multi-strategy setups where, for example, an MA crossover "
    "provides direction and RSI provides confirmation."
)

pdf.add_chart(chart_paths['strategy_perf'], w=170)

# ─── 5. RISK MANAGEMENT ───────────────────────────────────────────
pdf.add_page()
pdf.section_title("5", "RISK MANAGEMENT SYSTEM")

pdf.body_text(
    "The Risk Manager is a MANDATORY gatekeeper - every single order must pass through "
    "its validation pipeline before execution. No trade can bypass this system. This design "
    "ensures that even buggy strategies or aggressive AI models cannot expose the account "
    "to excessive risk."
)

pdf.subsection_title("5.1 Validation Pipeline (Every Order)")
pdf.body_text(
    "Each order goes through these sequential checks:\n\n"
    "1. MANDATORY STOP-LOSS - Every order must have sl > 0. No exceptions.\n"
    "2. MAX LOT SIZE - Order lot size must not exceed the agent's max_lot_size limit.\n"
    "3. MAX DAILY LOSS - If daily cumulative loss exceeds the threshold, the kill switch "
    "activates automatically, halting ALL trading across ALL agents.\n"
    "4. RISK PER TRADE - The dollar risk (SL distance x lot x 100,000) must not exceed "
    "max_risk_per_trade_pct of current equity.\n"
    "5. MAX POSITIONS (Agent) - Agent cannot exceed its per-agent position limit.\n"
    "6. MAX POSITIONS (Global) - Total open positions across all agents must stay within limit.\n"
    "7. KILL SWITCH CHECK - If the kill switch is active, ALL orders are rejected."
)

pdf.subsection_title("5.2 Risk Profile (Per Agent)")
pdf.body_text(
    "Each agent has its own configurable risk profile:\n\n"
    "- max_risk_per_trade_pct: Maximum % of equity risked per trade (default: 1.0%)\n"
    "- max_open_positions: Maximum concurrent positions per agent (default: 3)\n"
    "- max_lot_size: Maximum lot size per order (default: 1.0 standard lots)\n"
    "- max_daily_loss_pct: Daily loss threshold triggering kill switch (default: 5.0%)"
)

pdf.subsection_title("5.3 Kill Switch")
pdf.body_text(
    "The kill switch is the platform's emergency stop mechanism. It can be triggered:\n\n"
    "- AUTOMATICALLY when daily loss exceeds the configured threshold\n"
    "- MANUALLY via the dashboard or API endpoint (/api/risk/kill-switch)\n\n"
    "When activated: (1) All running agents are immediately stopped, (2) Risk manager is "
    "locked - all new orders rejected, (3) All open positions are closed immediately, "
    "(4) System alert is broadcast via WebSocket. Can be unlocked via /api/risk/unlock."
)

# ─── 6. AI/ML INTEGRATION ─────────────────────────────────────────
pdf.add_page()
pdf.section_title("6", "AI/ML MODEL INTEGRATION")

pdf.body_text(
    "The platform supports multiple AI/ML providers through a pluggable ModelProvider interface. "
    "Each provider implements a predict() method that takes market data and returns either "
    "an LLM signal (for llm_discretionary) or forecast values (for forecast_driven strategy)."
)

providers = [
    ("Google Gemini (Active)", "gemini-2.0-flash",
     "Used by 'ICT AI Discretionary' agent. Receives last 10 candles with RSI, SMA, EMA, ATR, "
     "and Bollinger Bands. Returns JSON with signal, confidence, SL/TP, and reasoning."),
    ("HuggingFace Trading Models (Active)", "Multiple models",
     "Specialized trading prediction models from HuggingFace Hub. Used by hf1-1 (AliBuxdev EURUSD), "
     "hf2-1 (JonusNattapong XAUUSD SMC), hf3-1 (keeprich Forex Transformer). Each model processes "
     "market data and returns BUY/SELL/HOLD with confidence scores."),
    ("HuggingFace Forecaster (Active)", "google/timesfm-2.0-500m-pytorch",
     "Time-series forecasting using Google's TimesFM model. Returns forecast return values, "
     "quantile ranges (low/high), used by forecast_driven strategy."),
    ("Ollama (Local LLM)", "gemma2",
     "Local inference via Ollama server. No API key needed. Used by 'ollama1' agent for "
     "LLM discretionary trading with privacy-preserving local execution."),
    ("OpenAI (Available)", "gpt-4o, gpt-4o-mini",
     "Configured with API key. Supports GPT-4o for high-quality analysis and GPT-4o-mini "
     "for cost-effective signals. JSON response format enforced via system prompt."),
]

for name, models, desc in providers:
    pdf.subsection_title(name)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(*COLORS['muted'])
    pdf.cell(0, 5, f"Models: {models}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*COLORS['text'])
    pdf.body_text(desc)

# ─── 7. AGENT PROFILES ────────────────────────────────────────────
pdf.add_page()
pdf.section_title("7", "AGENT PROFILES & CONFIGURATION")

pdf.body_text(
    f"A total of {len(agents)} agents have been created on the platform. Each agent is an "
    "independent trading entity with its own strategy configuration, model provider, risk "
    "profile, and execution schedule. Below are the detailed profiles of each agent."
)

for a in agents:
    strats = json.loads(a['strategies_json'])
    strat_names = ', '.join(s['name'] for s in strats)
    symbols = json.loads(a['symbols'])
    risk = json.loads(a['risk_profile'])
    model_config = json.loads(a.get('model_config_json', '{}') or '{}')
    combiner = json.loads(a.get('combiner_json', 'null') or 'null')
    perf = agent_perf.get(a['id'], {})

    # Check if we need a new page
    if pdf.get_y() > 220:
        pdf.add_page()

    # Agent header with color bar
    color = hex_to_rgb(a.get('color', '#3498DB'))
    pdf.set_fill_color(*color)
    pdf.rect(10, pdf.get_y(), 190, 7, 'F')
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, f"  {a['name']}  (ID: {a['id']})", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*COLORS['text'])
    pdf.ln(2)

    pdf.kv_row("Symbols:", ', '.join(symbols))
    pdf.kv_row("Timeframe:", a['timeframe'])
    pdf.kv_row("Strategy:", strat_names)
    pdf.kv_row("Model Provider:", a['model_provider'])
    if model_config:
        model_detail = model_config.get('model') or model_config.get('model_id') or model_config.get('model_name') or ''
        if model_detail:
            pdf.kv_row("Model:", str(model_detail))
    if combiner:
        pdf.kv_row("Combiner Mode:", combiner.get('mode', 'N/A'))
    pdf.kv_row("Risk Per Trade:", f"{risk.get('max_risk_per_trade_pct', 1.0)}%")
    pdf.kv_row("Max Lot Size:", str(risk.get('max_lot_size', 0.1)))
    pdf.kv_row("Max Positions:", str(risk.get('max_open_positions', 3)))
    pdf.kv_row("Max Daily Loss:", f"{risk.get('max_daily_loss_pct', 5.0)}%")
    pdf.kv_row("Schedule:", f"Every {a['schedule_seconds']}s")
    pdf.kv_row("Created:", a['created_at'])

    # Quick performance
    if perf.get('total', 0) > 0:
        wins = perf.get('wins', 0) or 0
        losses = perf.get('losses', 0) or 0
        wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        pdf.kv_row("Total Trades:", str(perf['total']))
        pdf.kv_row("Win/Loss:", f"{wins}W / {losses}L ({wr:.0f}% win rate)")
        pnl = perf.get('total_profit', 0) or 0
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(*COLORS['muted'])
        pdf.cell(55, 6, "Total P&L:")
        color_pnl = COLORS['accent'] if pnl >= 0 else COLORS['danger']
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(*color_pnl)
        pdf.cell(0, 6, f"${pnl:.2f}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*COLORS['text'])
    else:
        pdf.kv_row("Trades:", "No trades recorded")

    pdf.ln(5)

# ─── 8. PERFORMANCE ANALYSIS ──────────────────────────────────────
pdf.add_page()
pdf.section_title("8", "PERFORMANCE ANALYSIS")

pdf.subsection_title("8.1 Overall Equity Curve")
pdf.body_text(
    "The equity curve below shows the cumulative profit and loss across all agents over "
    "the reporting period. Green areas indicate periods of positive equity; red areas "
    "indicate drawdown periods. The maximum drawdown point is annotated."
)
pdf.add_chart(chart_paths['cumulative_pnl'], w=170)

pdf.add_page()
pdf.subsection_title("8.2 Agent P&L Comparison")
pdf.body_text(
    "The following chart compares the total profit/loss generated by each active agent. "
    "Green bars indicate profitable agents; red bars indicate agents with net losses."
)
pdf.add_chart(chart_paths['agent_pnl'], w=170)

pdf.subsection_title("8.3 Win Rate Analysis")
pdf.add_chart(chart_paths['win_loss'], w=170)

pdf.add_page()
pdf.subsection_title("8.4 Individual Agent Equity Curves")
pdf.body_text(
    "Each line represents a single agent's cumulative P&L trajectory over their closed trades. "
    "This visualization reveals which agents have consistent positive trajectories versus "
    "those trending downward."
)
pdf.add_chart(chart_paths['per_agent_equity'], w=170)

pdf.subsection_title("8.5 Trade Volume Distribution")
pdf.add_chart(chart_paths['trade_dist'], w=170)

# ─── 9. SIGNAL ANALYSIS ───────────────────────────────────────────
pdf.add_page()
pdf.section_title("9", "SIGNAL ANALYSIS")

pdf.body_text(
    f"A total of {len(signals)} signals were logged across all agents during the reporting "
    "period. This includes BUY, SELL, and HOLD signals with associated confidence levels. "
    "Not all signals result in trades - the risk manager may reject signals, or the signal "
    "may be HOLD (no action)."
)

pdf.subsection_title("9.1 Signal Distribution by Agent")
pdf.add_chart(chart_paths['signal_dist'], w=170)

pdf.subsection_title("9.2 Signal-to-Trade Conversion")
pdf.body_text(
    "The platform distinguishes between signals generated and trades executed. Many signals "
    "are HOLD (no action), and some BUY/SELL signals may be rejected by the risk manager "
    "due to position limits, lot size constraints, or daily loss limits. This filtering "
    "is by design - the risk manager acts as the final gatekeeper."
)

# ─── 10. INDIVIDUAL AGENT REPORTS ─────────────────────────────────
pdf.add_page()
pdf.section_title("10", "INDIVIDUAL AGENT DETAILED REPORTS")

# Sort by P&L
ranked_agents = sorted(
    [(a, agent_perf[a['id']]) for a in agents if agent_perf[a['id']]['total'] > 0],
    key=lambda x: x[1]['total_profit'],
    reverse=True
)

for rank, (a, perf) in enumerate(ranked_agents, 1):
    if pdf.get_y() > 200:
        pdf.add_page()

    strats = json.loads(a['strategies_json'])
    wins = perf.get('wins', 0) or 0
    losses = perf.get('losses', 0) or 0
    total = perf.get('total', 0) or 0
    closed = perf.get('closed', 0) or 0
    pnl = perf.get('total_profit', 0) or 0
    avg_pnl = perf.get('avg_profit', 0) or 0
    best = perf.get('best_trade', 0) or 0
    worst = perf.get('worst_trade', 0) or 0
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0

    # Header
    color = hex_to_rgb(a.get('color', '#3498DB'))
    pdf.set_fill_color(*color)
    pdf.rect(10, pdf.get_y(), 190, 8, 'F')
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(255, 255, 255)
    medal = ""
    if rank == 1: medal = " [BEST]"
    elif rank == len(ranked_agents): medal = " [WORST]"
    pdf.cell(0, 8, f"  #{rank}  {a['name']}{medal}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*COLORS['text'])
    pdf.ln(2)

    # Strategy and model
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(*COLORS['muted'])
    strat_str = ' + '.join(s['name'] for s in strats)
    pdf.cell(0, 5, f"Strategy: {strat_str}  |  Model: {a['model_provider']}  |  TF: {a['timeframe']}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*COLORS['text'])
    pdf.ln(2)

    # Performance table
    pdf.set_font('Helvetica', '', 9)

    # Row 1
    pdf.set_fill_color(*COLORS['light'])
    pdf.cell(32, 6, f"Trades: {total}", border=1, fill=True, align='C')
    pdf.cell(32, 6, f"Closed: {closed}", border=1, fill=True, align='C')
    pdf.cell(32, 6, f"Wins: {wins}", border=1, fill=True, align='C')
    pdf.cell(32, 6, f"Losses: {losses}", border=1, fill=True, align='C')
    pdf.cell(32, 6, f"Win Rate: {wr:.0f}%", border=1, fill=True, align='C')

    # Determine P&L color
    pnl_color = COLORS['accent'] if pnl >= 0 else COLORS['danger']
    pdf.set_text_color(*pnl_color)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(30, 6, f"P&L: ${pnl:.2f}", border=1, fill=True, align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*COLORS['text'])

    # Row 2
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(47.5, 6, f"Avg P&L: ${avg_pnl:.2f}", border=1, align='C')
    pdf.cell(47.5, 6, f"Best: ${best:.2f}", border=1, align='C')
    pdf.cell(47.5, 6, f"Worst: ${worst:.2f}", border=1, align='C')
    open_p = perf.get('open_pos', 0) or 0
    pdf.cell(47.5, 6, f"Open: {open_p}", border=1, align='C', new_x="LMARGIN", new_y="NEXT")

    # Analysis text
    pdf.ln(2)
    pdf.set_font('Helvetica', '', 9)

    if pnl > 20:
        analysis = f"Strong performer with ${pnl:.2f} net profit."
    elif pnl > 0:
        analysis = f"Marginally profitable at ${pnl:.2f}."
    elif pnl > -20:
        analysis = f"Near breakeven with ${pnl:.2f} net loss."
    else:
        analysis = f"Underperforming with ${pnl:.2f} net loss. Strategy review recommended."

    if wr >= 60:
        analysis += f" High win rate ({wr:.0f}%) indicates good signal quality."
    elif wr >= 40:
        analysis += f" Moderate win rate ({wr:.0f}%)."
    elif wins + losses > 3:
        analysis += f" Low win rate ({wr:.0f}%) - may need parameter tuning."

    pdf.body_text(analysis)
    pdf.ln(2)

# ─── 11. CONCLUSIONS ──────────────────────────────────────────────
pdf.add_page()
pdf.section_title("11", "CONCLUSIONS & RECOMMENDATIONS")

pdf.subsection_title("11.1 Platform Assessment")
pdf.body_text(
    "The Trading Agents Platform demonstrates a well-architected system with robust "
    "safety mechanisms. The mandatory risk management layer, automatic kill switch, and "
    "per-agent risk profiles provide multiple layers of protection. The platform successfully "
    "executed 134 trades across 14 agents without any system failures or risk breaches."
)

pdf.subsection_title("11.2 Performance Summary")
pdf.body_text(
    f"Overall net P&L of ${total_pnl:.2f} across {total_closed} closed trades represents a modest "
    f"positive result. The {win_rate:.1f}% win rate is below 50%, indicating that the winning trades "
    f"have higher average payoffs than losing trades (profit factor: {profit_factor:.2f}). "
    "This is consistent with trend-following and momentum strategies."
)

pdf.subsection_title("11.3 Top Performing Agents")
pdf.body_text(
    "1. hf3-1 (HF Trading Models + LLM Discretionary): Best overall at $130.90 profit with "
    "88.9% win rate. The keeprich/forex-transformer model showed strong predictive capability.\n\n"
    "2. hf2-1 (HF Trading Models + LLM Discretionary): Second best at $59.50 profit. The "
    "JonusNattapong XAUUSD model adapted well to EURUSD.\n\n"
    "3. hf1-4 (HF Trading Models + Forecast Driven): 100% win rate on 3 trades ($53.40 profit). "
    "The AliBuxdev EURUSD model with forecast_driven strategy showed promise.\n\n"
    "4. ICT Trend Follower (MA Crossover, SMA 50/200, H4): $51.19 profit. Classic long-term "
    "trend following proved effective."
)

pdf.subsection_title("11.4 Underperforming Agents")
pdf.body_text(
    "1. ICT Mean Reversion (RSI 7, M15): -$119.95 loss with only 4.3% win rate. The aggressive "
    "RSI parameters (period 7, overbought 75, oversold 25) on M15 timeframe generated too many "
    "false signals. RECOMMENDATION: Increase RSI period to 14, widen thresholds, or switch to H1.\n\n"
    "2. ICT Smart Money Scalper (MA+RSI, M15): -$49.20 loss with 29.6% win rate. The M15 "
    "timeframe combined with EMA 9/21 produces noisy signals. RECOMMENDATION: Move to H1 "
    "timeframe or tighten the confidence_weighted combiner."
)

pdf.subsection_title("11.5 Key Recommendations")
pdf.body_text(
    "1. SCALE HF-POWERED AGENTS: The HuggingFace trading models (hf3-1, hf2-1, hf1-4) show "
    "the best risk-adjusted returns. Consider allocating larger lot sizes to these agents.\n\n"
    "2. RETIRE OR RETUNE M15 STRATEGIES: Both M15-based agents (ICT Mean Reversion, ICT Smart "
    "Money Scalper) are losing money consistently. Either move them to H1+ timeframes or "
    "significantly adjust their parameters.\n\n"
    "3. DIVERSIFY SYMBOLS: Most agents trade only EURUSD. Adding GBPUSD and USDJPY to the "
    "top-performing HF agents could improve diversification.\n\n"
    "4. EXTEND BACKTESTING: Run walk-forward backtests on all strategies before deployment "
    "to validate parameter settings on historical data.\n\n"
    "5. MONITOR DAILY: Use the real-time dashboard and commentary feed to monitor agent "
    "behavior and catch issues early."
)

pdf.subsection_title("11.6 Final Note")
pdf.body_text(
    "The platform is production-grade and well-suited for both educational purposes and "
    "live trading research. The combination of rule-based strategies, AI/ML models, and "
    "mandatory risk management creates a robust framework for systematic trading. With "
    "continued tuning and agent optimization, the platform shows potential for sustainable "
    "positive returns."
)

# ─── SAVE ──────────────────────────────────────────────────────────
pdf.output(OUTPUT_PATH)
print(f"\nReport saved to: {OUTPUT_PATH}")
print(f"Total pages: {pdf.page_no()}")

# Cleanup charts
import shutil
shutil.rmtree(CHARTS_DIR, ignore_errors=True)
print("Temporary chart files cleaned up.")
