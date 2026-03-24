"""
AlgoTrader Dashboard - Streamlit App

Launch: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
import glob
from datetime import datetime


# --- Page Config ---
st.set_page_config(
    page_title="AlgoTrader Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Data Loading ---
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'historical')


@st.cache_data
def load_backtest_json(filepath):
    """Load a backtest result JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


@st.cache_data
def load_csv(filepath):
    """Load a CSV file."""
    return pd.read_csv(filepath)


@st.cache_data
def get_available_backtests():
    """Scan logs/ for backtest result files and return metadata."""
    pattern = os.path.join(LOGS_DIR, 'backtest_*.json')
    files = sorted(glob.glob(pattern), reverse=True)

    results = []
    for f in files:
        try:
            data = load_backtest_json(f)
            config = data.get('config', {})
            metrics = data.get('results', {}).get('metrics', {})
            strategy_name = config.get('strategy', {}).get('name', 'unknown')
            timestamp = os.path.basename(f).replace('backtest_', '').replace('.json', '')

            results.append({
                'filepath': f,
                'filename': os.path.basename(f),
                'timestamp': timestamp,
                'strategy': strategy_name,
                'return_pct': metrics.get('total_return_pct', 0),
                'win_rate': metrics.get('win_rate_pct', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'max_dd_pct': metrics.get('max_drawdown_pct', 0),
                'total_trades': metrics.get('total_trades', 0),
                'sharpe': metrics.get('sharpe_ratio', 0),
            })
        except Exception:
            continue

    return results


def format_timestamp(ts):
    """Format timestamp string to readable date."""
    try:
        dt = datetime.strptime(ts, '%Y%m%d_%H%M%S')
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ts


# --- Sidebar ---
st.sidebar.title("AlgoTrader")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Backtest Explorer", "Trade Analysis", "Strategy Comparison", "Market Data"]
)

# Load available backtests
backtests = get_available_backtests()

if not backtests:
    st.warning("No backtest results found in logs/. Run a backtest first.")
    st.stop()


# ============================================================
# PAGE: Overview
# ============================================================
if page == "Overview":
    st.title("Strategy Performance Overview")

    # Summary cards for best results by strategy
    strategies = list(set(b['strategy'] for b in backtests))

    # Find best run per strategy (by return)
    best_per_strategy = {}
    for s in strategies:
        runs = [b for b in backtests if b['strategy'] == s]
        best = max(runs, key=lambda x: x['return_pct'])
        best_per_strategy[s] = best

    # Display metric cards
    cols = st.columns(min(len(best_per_strategy), 4))
    for i, (strategy, best) in enumerate(best_per_strategy.items()):
        col = cols[i % len(cols)]
        with col:
            st.metric(
                label=strategy.replace('_', ' ').title(),
                value=f"{best['return_pct']:.2f}%",
                delta=f"PF {best['profit_factor']:.2f}"
            )
            st.caption(
                f"WR: {best['win_rate']:.1f}% | DD: {best['max_dd_pct']:.1f}% | "
                f"Trades: {best['total_trades']}"
            )

    st.markdown("---")

    # Strategy comparison scatter plot
    st.subheader("All Backtest Runs: Return vs. Risk")

    df_all = pd.DataFrame(backtests)
    fig = px.scatter(
        df_all,
        x='max_dd_pct',
        y='return_pct',
        color='strategy',
        size='total_trades',
        hover_data=['profit_factor', 'win_rate', 'sharpe', 'timestamp'],
        labels={
            'max_dd_pct': 'Max Drawdown %',
            'return_pct': 'Total Return %',
            'strategy': 'Strategy'
        },
        size_max=20
    )
    fig.update_layout(height=500)
    # Invert x-axis so less drawdown is to the right (better)
    fig.update_xaxes(autorange='reversed')
    st.plotly_chart(fig, use_container_width=True)

    # Recent runs table
    st.subheader("Recent Backtest Runs")
    recent = df_all.head(20).copy()
    recent['date'] = recent['timestamp'].apply(format_timestamp)
    st.dataframe(
        recent[['date', 'strategy', 'return_pct', 'win_rate', 'profit_factor',
                'max_dd_pct', 'total_trades', 'sharpe']].reset_index(drop=True),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# PAGE: Backtest Explorer
# ============================================================
elif page == "Backtest Explorer":
    st.title("Backtest Explorer")

    # File selector
    display_names = [
        f"{b['strategy']} | {format_timestamp(b['timestamp'])} | "
        f"{b['return_pct']:+.2f}% | PF {b['profit_factor']:.2f}"
        for b in backtests
    ]

    selected_idx = st.sidebar.selectbox(
        "Select Backtest",
        range(len(display_names)),
        format_func=lambda i: display_names[i]
    )

    selected = backtests[selected_idx]
    data = load_backtest_json(selected['filepath'])
    config = data.get('config', {})
    results = data.get('results', {})
    metrics = results.get('metrics', {})
    trades = results.get('trades', [])

    # --- Key Metrics Row ---
    st.subheader("Performance Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Return", f"{metrics.get('total_return_pct', 0):.2f}%")
    c2.metric("Win Rate", f"{metrics.get('win_rate_pct', 0):.1f}%")
    c3.metric("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}")
    c4.metric("Max Drawdown", f"{metrics.get('max_drawdown_pct', 0):.1f}%")
    c5.metric("Sharpe", f"{metrics.get('sharpe_ratio', 0):.2f}")
    c6.metric("Trades", f"{metrics.get('total_trades', 0)}")

    st.markdown("---")

    # --- Equity Curve ---
    st.subheader("Equity Curve")

    # Try to load equity curve CSV
    eq_file = selected['filepath'].replace('backtest_', 'equity_curve_')
    if os.path.exists(eq_file):
        eq_df = load_csv(eq_file)
        eq_df['time'] = pd.to_datetime(eq_df['time'])

        fig_eq = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.7, 0.3],
            vertical_spacing=0.05,
            subplot_titles=("Equity", "Drawdown %")
        )

        fig_eq.add_trace(
            go.Scatter(
                x=eq_df['time'], y=eq_df['equity'],
                mode='lines', name='Equity',
                line=dict(color='#2196F3', width=2)
            ), row=1, col=1
        )

        fig_eq.add_trace(
            go.Scatter(
                x=eq_df['time'], y=eq_df['drawdown_pct'],
                fill='tozeroy', name='Drawdown',
                line=dict(color='#F44336', width=1),
                fillcolor='rgba(244, 67, 54, 0.3)'
            ), row=2, col=1
        )

        fig_eq.update_layout(height=500, showlegend=False)
        fig_eq.update_yaxes(title_text="Equity ($)", row=1, col=1)
        fig_eq.update_yaxes(title_text="Drawdown %", row=2, col=1)
        st.plotly_chart(fig_eq, use_container_width=True)
    else:
        # Fall back to equity curve from JSON
        eq_data = results.get('equity_curve', [])
        if eq_data:
            eq_df = pd.DataFrame(eq_data)
            eq_df['time'] = pd.to_datetime(eq_df['time'])
            fig_eq = go.Figure(go.Scatter(
                x=eq_df['time'], y=eq_df['equity'],
                mode='lines', name='Equity'
            ))
            fig_eq.update_layout(height=400)
            st.plotly_chart(fig_eq, use_container_width=True)

    # --- Trade P&L Distribution ---
    if trades:
        st.subheader("Trade Analysis")

        trades_df = pd.DataFrame(trades)
        trades_df['pnl'] = pd.to_numeric(trades_df['pnl'], errors='coerce')

        col1, col2 = st.columns(2)

        with col1:
            # P&L Distribution
            fig_dist = go.Figure()
            wins = trades_df[trades_df['pnl'] > 0]['pnl']
            losses = trades_df[trades_df['pnl'] <= 0]['pnl']

            fig_dist.add_trace(go.Histogram(
                x=wins, name='Wins', marker_color='#4CAF50',
                opacity=0.7, nbinsx=20
            ))
            fig_dist.add_trace(go.Histogram(
                x=losses, name='Losses', marker_color='#F44336',
                opacity=0.7, nbinsx=20
            ))
            fig_dist.update_layout(
                title="Trade P&L Distribution",
                xaxis_title="P&L ($)",
                yaxis_title="Count",
                barmode='overlay',
                height=350
            )
            st.plotly_chart(fig_dist, use_container_width=True)

        with col2:
            # Cumulative P&L
            trades_df['cum_pnl'] = trades_df['pnl'].cumsum()
            fig_cum = go.Figure(go.Scatter(
                x=list(range(1, len(trades_df) + 1)),
                y=trades_df['cum_pnl'],
                mode='lines+markers',
                marker=dict(
                    color=trades_df['pnl'].apply(
                        lambda x: '#4CAF50' if x > 0 else '#F44336'
                    ),
                    size=6
                ),
                line=dict(color='#2196F3', width=2)
            ))
            fig_cum.update_layout(
                title="Cumulative P&L by Trade",
                xaxis_title="Trade #",
                yaxis_title="Cumulative P&L ($)",
                height=350
            )
            st.plotly_chart(fig_cum, use_container_width=True)

        # Exit reason breakdown
        col3, col4 = st.columns(2)
        with col3:
            if 'exit_reason' in trades_df.columns:
                exit_counts = trades_df['exit_reason'].value_counts()
                fig_exit = go.Figure(go.Pie(
                    labels=exit_counts.index,
                    values=exit_counts.values,
                    hole=0.4
                ))
                fig_exit.update_layout(title="Exit Reasons", height=350)
                st.plotly_chart(fig_exit, use_container_width=True)

        with col4:
            if 'direction' in trades_df.columns:
                dir_stats = trades_df.groupby('direction').agg(
                    trades=('pnl', 'count'),
                    total_pnl=('pnl', 'sum'),
                    avg_pnl=('pnl', 'mean'),
                    win_rate=('pnl', lambda x: (x > 0).mean() * 100)
                ).round(2)
                st.markdown("**Performance by Direction**")
                st.dataframe(dir_stats, use_container_width=True)

    # --- Config Details ---
    with st.expander("Strategy Configuration"):
        st.json(config.get('strategy', {}))


# ============================================================
# PAGE: Trade Analysis
# ============================================================
elif page == "Trade Analysis":
    st.title("Trade Analysis")

    # Select a backtest
    display_names = [
        f"{b['strategy']} | {format_timestamp(b['timestamp'])} | "
        f"{b['return_pct']:+.2f}%"
        for b in backtests
    ]

    selected_idx = st.sidebar.selectbox(
        "Select Backtest",
        range(len(display_names)),
        format_func=lambda i: display_names[i]
    )

    selected = backtests[selected_idx]
    data = load_backtest_json(selected['filepath'])
    trades = data.get('results', {}).get('trades', [])

    if not trades:
        st.warning("No trades in this backtest.")
        st.stop()

    trades_df = pd.DataFrame(trades)
    trades_df['pnl'] = pd.to_numeric(trades_df['pnl'], errors='coerce')
    trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
    trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])

    # Monthly returns heatmap
    st.subheader("Monthly Returns Heatmap")
    trades_df['month'] = trades_df['entry_time'].dt.to_period('M')
    monthly = trades_df.groupby('month')['pnl'].sum()

    if len(monthly) > 0:
        monthly_df = monthly.reset_index()
        monthly_df['month'] = monthly_df['month'].astype(str)
        monthly_df['year'] = monthly_df['month'].str[:4]
        monthly_df['mo'] = monthly_df['month'].str[5:7]

        pivot = monthly_df.pivot_table(
            values='pnl', index='year', columns='mo', aggfunc='sum'
        )
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        pivot.columns = [month_names[int(c)-1] for c in pivot.columns]

        fig_heat = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale='RdYlGn',
            zmid=0,
            text=np.round(pivot.values, 1),
            texttemplate='$%{text}',
            textfont={"size": 11},
        ))
        fig_heat.update_layout(
            title="Monthly P&L ($)",
            height=250,
            yaxis=dict(autorange='reversed')
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # Hour-of-day analysis
    st.subheader("Performance by Hour of Day")
    trades_df['hour'] = trades_df['entry_time'].dt.hour
    hourly = trades_df.groupby('hour').agg(
        trades=('pnl', 'count'),
        total_pnl=('pnl', 'sum'),
        avg_pnl=('pnl', 'mean'),
        win_rate=('pnl', lambda x: (x > 0).mean() * 100)
    ).round(2)

    fig_hour = go.Figure()
    colors = ['#4CAF50' if v > 0 else '#F44336' for v in hourly['total_pnl']]
    fig_hour.add_trace(go.Bar(
        x=hourly.index, y=hourly['total_pnl'],
        marker_color=colors, name='Total P&L'
    ))
    fig_hour.update_layout(
        xaxis_title="Hour (UTC)", yaxis_title="Total P&L ($)",
        height=350
    )
    st.plotly_chart(fig_hour, use_container_width=True)

    # Day-of-week analysis
    st.subheader("Performance by Day of Week")
    trades_df['dow'] = trades_df['entry_time'].dt.day_name()
    dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    dow = trades_df.groupby('dow').agg(
        trades=('pnl', 'count'),
        total_pnl=('pnl', 'sum'),
        avg_pnl=('pnl', 'mean'),
        win_rate=('pnl', lambda x: (x > 0).mean() * 100)
    ).reindex(dow_order).dropna().round(2)

    col1, col2 = st.columns(2)
    with col1:
        colors_dow = ['#4CAF50' if v > 0 else '#F44336' for v in dow['total_pnl']]
        fig_dow = go.Figure(go.Bar(
            x=dow.index, y=dow['total_pnl'], marker_color=colors_dow
        ))
        fig_dow.update_layout(
            title="P&L by Day of Week",
            yaxis_title="Total P&L ($)", height=300
        )
        st.plotly_chart(fig_dow, use_container_width=True)
    with col2:
        st.dataframe(dow, use_container_width=True)

    # MAE/MFE analysis
    if 'mae' in trades_df.columns and 'mfe' in trades_df.columns:
        st.subheader("MAE / MFE Analysis")
        st.caption(
            "Maximum Adverse Excursion (worst unrealized loss) vs "
            "Maximum Favorable Excursion (best unrealized gain) per trade"
        )

        trades_df['mae'] = pd.to_numeric(trades_df['mae'], errors='coerce')
        trades_df['mfe'] = pd.to_numeric(trades_df['mfe'], errors='coerce')

        fig_mae = go.Figure()
        fig_mae.add_trace(go.Scatter(
            x=trades_df['mae'],
            y=trades_df['mfe'],
            mode='markers',
            marker=dict(
                color=trades_df['pnl'].apply(
                    lambda x: '#4CAF50' if x > 0 else '#F44336'
                ),
                size=8, opacity=0.7
            ),
            text=trades_df.apply(
                lambda r: f"P&L: ${r['pnl']:.0f}<br>"
                          f"Direction: {r.get('direction', '?')}<br>"
                          f"Exit: {r.get('exit_reason', '?')}",
                axis=1
            ),
            hoverinfo='text'
        ))
        fig_mae.update_layout(
            xaxis_title="MAE (worst unrealized loss, points)",
            yaxis_title="MFE (best unrealized gain, points)",
            height=400
        )
        st.plotly_chart(fig_mae, use_container_width=True)

    # Full trades table
    st.subheader("All Trades")
    display_cols = ['entry_time', 'exit_time', 'direction', 'entry_price',
                    'exit_price', 'pnl', 'exit_reason', 'bars_held']
    available_cols = [c for c in display_cols if c in trades_df.columns]
    st.dataframe(
        trades_df[available_cols].sort_values('entry_time', ascending=False),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# PAGE: Strategy Comparison
# ============================================================
elif page == "Strategy Comparison":
    st.title("Strategy Comparison")

    strategies = list(set(b['strategy'] for b in backtests))

    selected_strategies = st.sidebar.multiselect(
        "Select Strategies to Compare",
        strategies,
        default=strategies[:3]
    )

    if not selected_strategies:
        st.info("Select at least one strategy from the sidebar.")
        st.stop()

    # Get best run per selected strategy
    comparison = []
    for s in selected_strategies:
        runs = [b for b in backtests if b['strategy'] == s]
        best = max(runs, key=lambda x: x['return_pct'])
        comparison.append(best)

    comp_df = pd.DataFrame(comparison)

    # Comparison table
    st.subheader("Best Run per Strategy")
    display = comp_df[['strategy', 'return_pct', 'win_rate', 'profit_factor',
                       'max_dd_pct', 'total_trades', 'sharpe']].copy()
    display.columns = ['Strategy', 'Return %', 'Win Rate %', 'Profit Factor',
                       'Max DD %', 'Trades', 'Sharpe']
    st.dataframe(display, use_container_width=True, hide_index=True)

    # Radar chart comparison
    st.subheader("Radar Comparison")

    categories = ['Return %', 'Win Rate %', 'Profit Factor', 'Sharpe', 'Trades']
    fig_radar = go.Figure()

    for _, row in comp_df.iterrows():
        # Normalize values for radar (0-100 scale)
        max_ret = max(comp_df['return_pct'].max(), 1)
        max_pf = max(comp_df['profit_factor'].max(), 1)
        max_sharpe = max(comp_df['sharpe'].max(), 0.1)
        max_trades = max(comp_df['total_trades'].max(), 1)

        values = [
            (row['return_pct'] / max_ret) * 100,
            row['win_rate'],
            (row['profit_factor'] / max_pf) * 100,
            (row['sharpe'] / max_sharpe) * 100,
            (row['total_trades'] / max_trades) * 100,
        ]
        values.append(values[0])  # close the polygon

        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            fill='toself',
            name=row['strategy'],
            opacity=0.6
        ))

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=450
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Overlay equity curves
    st.subheader("Equity Curve Overlay")
    fig_overlay = go.Figure()

    for item in comparison:
        eq_file = item['filepath'].replace('backtest_', 'equity_curve_')
        if os.path.exists(eq_file):
            eq_df = load_csv(eq_file)
            eq_df['time'] = pd.to_datetime(eq_df['time'])
            fig_overlay.add_trace(go.Scatter(
                x=eq_df['time'], y=eq_df['equity'],
                mode='lines', name=item['strategy'],
                line=dict(width=2)
            ))

    fig_overlay.update_layout(
        yaxis_title="Equity ($)",
        height=400,
        hovermode='x unified'
    )
    st.plotly_chart(fig_overlay, use_container_width=True)


# ============================================================
# PAGE: Market Data
# ============================================================
elif page == "Market Data":
    st.title("Market Data Viewer")

    # Find data files
    data_files = []
    if os.path.exists(DATA_DIR):
        data_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]

    if not data_files:
        st.warning("No data files found in data/historical/")
        st.stop()

    selected_file = st.sidebar.selectbox("Select Data File", data_files)
    filepath = os.path.join(DATA_DIR, selected_file)

    @st.cache_data
    def load_market_data(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df

    df = load_market_data(filepath)

    st.markdown(f"**{selected_file}** | {len(df):,} bars | "
                f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")

    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start Date", df.index[0].date())
    with col2:
        end = st.date_input("End Date", df.index[-1].date())

    mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
    filtered = df[mask]

    # Candlestick chart with volume
    st.subheader("Price Chart")

    # Downsample if too many bars for performance
    max_bars = 5000
    if len(filtered) > max_bars:
        step = len(filtered) // max_bars
        plot_df = filtered.iloc[::step]
        st.caption(f"Showing 1 in {step} bars for performance ({len(plot_df):,} bars displayed)")
    else:
        plot_df = filtered

    fig_price = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03
    )

    fig_price.add_trace(go.Candlestick(
        x=plot_df.index,
        open=plot_df['open'], high=plot_df['high'],
        low=plot_df['low'], close=plot_df['close'],
        name='Price'
    ), row=1, col=1)

    if 'volume' in plot_df.columns:
        fig_price.add_trace(go.Bar(
            x=plot_df.index, y=plot_df['volume'],
            name='Volume', marker_color='rgba(100, 150, 200, 0.5)'
        ), row=2, col=1)

    fig_price.update_layout(
        height=600,
        xaxis_rangeslider_visible=False,
        showlegend=False
    )
    fig_price.update_yaxes(title_text="Price", row=1, col=1)
    fig_price.update_yaxes(title_text="Volume", row=2, col=1)
    st.plotly_chart(fig_price, use_container_width=True)

    # Data stats
    st.subheader("Data Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Bars", f"{len(filtered):,}")
    col2.metric("Avg Close", f"${filtered['close'].mean():,.2f}")
    col3.metric("Price Range",
                f"${filtered['low'].min():,.0f} - ${filtered['high'].max():,.0f}")
    if 'volume' in filtered.columns:
        col4.metric("Avg Volume", f"{filtered['volume'].mean():,.0f}")


# --- Footer ---
st.sidebar.markdown("---")
st.sidebar.caption("AlgoTrader Dashboard v1.0")
st.sidebar.caption("Built with Streamlit (free & open source)")
