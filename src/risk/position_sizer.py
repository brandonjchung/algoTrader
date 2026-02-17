"""
Position Sizing & Risk Management Module

Provides Kelly-based position sizing and portfolio-level risk controls.
Can be used standalone for analysis or integrated into the backtester.

Key functions:
  - half_kelly_size(): Position size based on recent win rate and payoff ratio
  - drawdown_scaler(): Reduce position when in drawdown
  - portfolio_risk_check(): Cross-strategy correlation and exposure limits
  - confidence_score(): Rolling OOS performance score for a strategy
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Calculate Kelly criterion fraction.

    Kelly f* = W - (1-W)/R where W=win rate, R=avg_win/avg_loss ratio.
    Returns the fraction of capital to risk (0 to 1).
    Negative values mean the strategy has negative expectancy.
    """
    if avg_loss == 0 or avg_win == 0:
        return 0.0
    R = abs(avg_win / avg_loss)
    W = win_rate
    f = W - (1 - W) / R
    return f


def half_kelly_size(trades: List[Dict], lookback: int = 20,
                    base_contracts: int = 1) -> Dict:
    """Calculate half-Kelly position size from recent trades.

    Half-Kelly is standard practice: full Kelly is too aggressive,
    half-Kelly provides ~75% of the growth rate with much less variance.

    Args:
        trades: List of trade dicts with 'pnl' key
        lookback: Number of recent trades to consider
        base_contracts: Maximum position size (scales down from this)

    Returns:
        Dict with kelly_f, half_kelly_f, recommended_size, stats
    """
    if len(trades) < 5:
        return {
            'kelly_f': 0,
            'half_kelly_f': 0,
            'recommended_size': base_contracts,
            'reason': f'insufficient trades ({len(trades)} < 5 minimum)',
            'win_rate': 0,
            'payoff_ratio': 0,
        }

    recent = trades[-lookback:] if len(trades) > lookback else trades
    pnls = [t['pnl'] for t in recent]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / len(recent) if recent else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0

    f = kelly_fraction(win_rate, avg_win, avg_loss)
    half_f = max(0, f / 2)

    # Convert fraction to contracts (discrete sizing)
    if half_f <= 0:
        recommended = 0  # negative expectancy -> don't trade
        reason = 'negative expectancy'
    elif half_f < 0.05:
        recommended = max(1, int(base_contracts * 0.5))
        reason = 'minimal edge'
    elif half_f < 0.15:
        recommended = base_contracts
        reason = 'moderate edge'
    else:
        recommended = base_contracts  # cap at base, don't over-leverage
        reason = 'strong edge (capped at base)'

    return {
        'kelly_f': round(f, 4),
        'half_kelly_f': round(half_f, 4),
        'recommended_size': recommended,
        'reason': reason,
        'win_rate': round(win_rate, 4),
        'payoff_ratio': round(avg_win / avg_loss, 2) if avg_loss > 0 else 0,
        'recent_trades': len(recent),
        'expectancy_per_trade': round(np.mean(pnls), 2),
    }


def drawdown_scaler(current_equity: float, peak_equity: float,
                    dd_levels: Optional[Dict] = None) -> Dict:
    """Scale position size based on current drawdown.

    Default levels:
      0-5% DD:  100% size (normal)
      5-10% DD: 50% size (cautious)
      10-15% DD: 25% size (defensive)
      15%+ DD:  0% size (stop trading)

    Args:
        current_equity: Current portfolio equity
        peak_equity: All-time high equity
        dd_levels: Optional custom {dd_pct: scale_factor} dict

    Returns:
        Dict with drawdown_pct, scale_factor, action
    """
    if dd_levels is None:
        dd_levels = {
            0: 1.0,    # no drawdown: full size
            5: 0.5,    # -5%: half size
            10: 0.25,  # -10%: quarter size
            15: 0.0,   # -15%: stop trading
        }

    if peak_equity <= 0:
        return {'drawdown_pct': 0, 'scale_factor': 1.0, 'action': 'normal'}

    dd_pct = ((peak_equity - current_equity) / peak_equity) * 100

    # Find applicable level
    scale = 1.0
    for level in sorted(dd_levels.keys(), reverse=True):
        if dd_pct >= level:
            scale = dd_levels[level]
            break

    if scale == 0:
        action = 'STOP - max drawdown exceeded'
    elif scale < 0.5:
        action = 'DEFENSIVE - reduced to 25%'
    elif scale < 1.0:
        action = 'CAUTIOUS - reduced to 50%'
    else:
        action = 'normal'

    return {
        'drawdown_pct': round(dd_pct, 2),
        'scale_factor': scale,
        'action': action,
    }


def confidence_score(trades: List[Dict], lookback: int = 30) -> Dict:
    """Calculate a rolling confidence score for a strategy.

    Score 0-100 based on:
      - Recent win rate (vs historical)
      - Recent PF (vs 1.0 threshold)
      - Drawdown trend (improving or worsening)
      - Trade frequency (enough to be statistically meaningful)

    Args:
        trades: Full list of trade dicts with 'pnl' key
        lookback: Recent trades window

    Returns:
        Dict with score (0-100), components, recommendation
    """
    if len(trades) < 10:
        return {
            'score': 50,
            'recommendation': 'INSUFFICIENT DATA',
            'components': {},
        }

    recent = trades[-lookback:] if len(trades) > lookback else trades
    older = trades[:-lookback] if len(trades) > lookback else []

    recent_pnls = [t['pnl'] for t in recent]
    recent_wr = sum(1 for p in recent_pnls if p > 0) / len(recent_pnls)

    # Component 1: Win rate score (0-30)
    # 50% WR = 15 points, 60% = 25, 40% = 5
    wr_score = max(0, min(30, (recent_wr - 0.3) * 100))

    # Component 2: Profit factor score (0-30)
    recent_wins = [p for p in recent_pnls if p > 0]
    recent_losses = [abs(p) for p in recent_pnls if p <= 0]
    gross_profit = sum(recent_wins)
    gross_loss = sum(recent_losses)
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    pf_score = max(0, min(30, (pf - 0.5) * 20))

    # Component 3: Trend score (0-20) - is performance improving?
    if len(recent_pnls) >= 10:
        first_half = recent_pnls[:len(recent_pnls)//2]
        second_half = recent_pnls[len(recent_pnls)//2:]
        trend = np.mean(second_half) - np.mean(first_half)
        trend_score = max(0, min(20, 10 + trend * 2))
    else:
        trend_score = 10  # neutral

    # Component 4: Consistency score (0-20) - low variance is better
    if len(recent_pnls) >= 5:
        cv = np.std(recent_pnls) / abs(np.mean(recent_pnls)) if np.mean(recent_pnls) != 0 else 10
        consistency_score = max(0, min(20, 20 - cv * 2))
    else:
        consistency_score = 10

    total = wr_score + pf_score + trend_score + consistency_score

    if total >= 70:
        rec = 'HIGH CONFIDENCE - full allocation'
    elif total >= 50:
        rec = 'MODERATE - standard allocation'
    elif total >= 30:
        rec = 'LOW - reduce allocation'
    else:
        rec = 'VERY LOW - consider pausing'

    return {
        'score': round(total, 1),
        'recommendation': rec,
        'components': {
            'win_rate': round(wr_score, 1),
            'profit_factor': round(pf_score, 1),
            'trend': round(trend_score, 1),
            'consistency': round(consistency_score, 1),
        },
        'recent_wr': round(recent_wr, 3),
        'recent_pf': round(pf, 2),
    }


def portfolio_risk_check(strategy_trades: Dict[str, List[Dict]],
                         lookback_days: int = 30) -> Dict:
    """Check portfolio-level risk across multiple strategies.

    Detects:
      - Simultaneous drawdowns (correlation spike)
      - Concentration risk (one strategy dominating P&L)
      - Overall portfolio health

    Args:
        strategy_trades: {strategy_name: [trade_dicts]} with 'entry_time' and 'pnl'

    Returns:
        Dict with correlation info, concentration, alerts
    """
    if len(strategy_trades) < 2:
        return {'alert': 'Need 2+ strategies for portfolio risk check'}

    # Build daily P&L series per strategy
    daily_pnl = {}
    for name, trades in strategy_trades.items():
        if not trades:
            continue
        df = pd.DataFrame(trades)
        if 'exit_time' in df.columns:
            df['date'] = pd.to_datetime(df['exit_time']).dt.date
        elif 'entry_time' in df.columns:
            df['date'] = pd.to_datetime(df['entry_time']).dt.date
        else:
            continue
        daily = df.groupby('date')['pnl'].sum()
        daily_pnl[name] = daily

    if len(daily_pnl) < 2:
        return {'alert': 'Not enough daily P&L data for correlation analysis'}

    # Align and compute correlation
    aligned = pd.DataFrame(daily_pnl).fillna(0)
    corr = aligned.corr()

    # Check for dangerous positive correlation
    alerts = []
    for i, col1 in enumerate(corr.columns):
        for col2 in corr.columns[i+1:]:
            r = corr.loc[col1, col2]
            if r > 0.5:
                alerts.append(f'HIGH CORRELATION: {col1} vs {col2} = {r:.2f} '
                              f'(strategies losing/winning together)')
            elif r < -0.3:
                alerts.append(f'GOOD: {col1} vs {col2} = {r:.2f} (negative correlation)')

    # Concentration: what % of total P&L comes from each strategy?
    total_pnl = {name: sum(t['pnl'] for t in trades)
                 for name, trades in strategy_trades.items() if trades}
    abs_total = sum(abs(v) for v in total_pnl.values())
    concentration = {name: abs(pnl) / abs_total * 100 if abs_total > 0 else 0
                     for name, pnl in total_pnl.items()}

    for name, pct in concentration.items():
        if pct > 80:
            alerts.append(f'CONCENTRATION: {name} = {pct:.0f}% of absolute P&L')

    # Simultaneous losing days
    losing_days = (aligned < 0).sum(axis=1)
    simultaneous_losses = (losing_days == len(aligned.columns)).sum()
    total_days = len(aligned)
    if total_days > 0:
        simul_pct = simultaneous_losses / total_days * 100
        if simul_pct > 20:
            alerts.append(f'SIMULTANEOUS LOSSES: {simul_pct:.0f}% of days all strategies lost')

    return {
        'correlation': corr.to_dict(),
        'concentration': concentration,
        'total_pnl': total_pnl,
        'simultaneous_loss_days': simultaneous_losses,
        'total_trading_days': total_days,
        'alerts': alerts if alerts else ['Portfolio risk within normal parameters'],
    }
