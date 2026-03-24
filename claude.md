# AlgoTrader Development Methodology

## User Preferences
- **Always prefer free/open-source tools** over paid alternatives
- **Standard best practices** for all code (clean, documented, tested)
- Dashboard built with Streamlit (free, open source): `python -m streamlit run dashboard.py`
- **Proactively suggest workflow improvements** whenever you see an opportunity to make things more efficient (scripts, automation, shortcuts, tooling). Don't wait to be asked.

## Project Structure

```
algoTrader/
├── claude.md                  # This file - methodology & rules
├── README.md                  # Project overview
├── QUICKSTART.md              # Getting started guide
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── docker-compose.yml         # Monitoring stack
│
├── config/                    # All configuration files
│   ├── strategies/
│   │   ├── production/        # Validated strategies ready for forward testing
│   │   │   ├── mean_rev_quiet_filter.yaml   # V2 (current best)
│   │   │   └── mean_rev_atr_filter.yaml     # V1 reference
│   │   ├── development/       # Strategies being built/tested
│   │   │   ├── trend_following_v1.yaml      # Breakout complement to MR
│   │   │   ├── ema_crossover_v1.yaml        # Raw EMA 9 baseline
│   │   │   ├── ema_crossover_v1_filtered.yaml
│   │   │   ├── ema_crossover_v2_strong.yaml # Best EMA variant (PF 0.99)
│   │   │   └── ema_crossover_v3_balanced.yaml
│   │   └── archive/           # Tested/superseded configs
│   │       └── ...            # 22 archived configs from rounds 1-5
│   └── grafana_dashboard.json         # Grafana config
│
├── src/                       # Source code
│   ├── strategies/            # Strategy implementations
│   │   ├── adaptive_market_strategy.py  # Mean reversion (production)
│   │   ├── trend_following_strategy.py  # Breakout/trend (development)
│   │   ├── ema_crossover_strategy.py    # EMA 9 crossover (development)
│   ├── backtest/              # Backtesting engine
│   ├── ib/                    # Interactive Brokers integration
│   ├── analysis/              # Market analysis tools
│   ├── monitoring/            # Monitoring & alerting
│   ├── risk/                  # Risk management
│   └── utils/                 # Shared utilities
│
├── tools/                     # Analysis & testing tools
│   ├── walk_forward_test.py   # Walk-forward validation framework
│   ├── component_test.py      # Single-variable component testing
│   ├── calibrate_filters.py   # Measure indicator distributions on real data
│   ├── regime_analysis.py     # Market regime analysis
│   ├── compare_strategies.py  # Side-by-side strategy comparison
│   └── debug/                 # Debug utilities
│
├── docs/                      # Documentation
│   ├── expert_review.md
│   ├── ib_setup_guide.md
│   └── ...
│
├── data/                      # Market data
│   └── historical/            # Historical OHLCV data files
│
└── logs/                      # Backtest results & trade logs
```

### Rules for keeping it organized:
- **Configs** go in `config/strategies/` - never in root
- **Tools/scripts** go in `tools/` - never in root
- **Docs** go in `docs/` - never in root
- **One-off analysis scripts** should be deleted after findings are captured
- **Root directory** should only have: claude.md, README, requirements.txt, .env, docker-compose

### Base config inheritance
`config/base.yaml` contains shared trading/contract/costs/risk/data/backtest settings.
Strategy configs in production/development/ inherit from base automatically via deep merge.
Strategy configs only need to define the `strategy:` section (and any overrides).
Standalone configs that include all sections still work unchanged (base values are overridden).

## Session Efficiency Guidelines

These rules reduce token usage without sacrificing thoroughness. Follow on every session.

### Windows PowerShell (user is on Windows)
- Replace `| tail -N` with `| Select-Object -Last N`
- Replace `| grep "pattern"` with `| Select-String "pattern"`
- Example: `python src/backtest/run_backtest.py ... | Select-Object -Last 15`
- Example: `python tools/rolling_walk_forward.py ... | Select-String "Test|Window"`

### Backtest output
- Always pipe through `| tail -15` (Linux) or `| Select-Object -Last 15` (Windows) for full backtests
- For walk-forward: pipe through `| grep -E "(WF\||Period|Train|Test|Validate)"` (Linux) or `| Select-String "Test|Window"` (Windows)
- When running multiple backtests, use background tasks and read JSON results
- JSON results path is always in the last line of output: `logs/backtest_*.json`

### File operations
- Use offset/limit on Read for files already partially known (don't re-read 400-line files)
- On session continuations, skip full codebase exploration -- the structure is documented here
- When creating test configs that inherit from base.yaml, only write the strategy section + overrides

### Config creation
- New strategy configs should be ~20 lines (strategy section only), not 80+ lines
- Example minimal config:
```yaml
strategy:
  name: "trend_following"
  breakout_period: 40
  # ... strategy-specific params only
logging:
  log_file: "logs/tf_wide_breakout.log"
```

### What NOT to cut
- Always read strategy code before modifying it (no blind edits)
- Always run walk-forward on any config being considered for ADOPT
- Always check yearly performance distribution on full backtests (regime dependency)
- Never skip the calibration step when setting new filter thresholds

## Strategy Development History

### V1 Baseline (config/strategies/adaptive_market.yaml)
- **Return:** +6.28%, 149 trades, 48.8% WR, PF 1.21
- **Walk-forward:** Train +4.22%, Test -4.90%, Validate +3.16%
- **Problem:** Test period failed badly; regime analysis found ATR increased 73.9% after peak

### V1 + ATR Filter (config/strategies/v1_atr_filter.yaml) — FIRST ADOPT
- **Change:** Added volatility filter: max_atr_for_entry: 5.0, min_atr_for_entry: 1.5
- **Evidence:** "Very High" ATR quintile lost -$873 (all net losses). Mean reversion fails in high volatility.
- **Result:** +10.31%, 86 trades, 48.8% WR, PF 1.61, MaxDD -3.70%
- **Walk-forward:** Train +7.64%, Test +0.36%, Validate +0.86% (all positive)

### Component Tests Run (10 single-change tests against V1+ATR baseline)
```
Round 1: RSI/time filter tests
  no_time_filter:  REJECT (validate -5.46% - clear overfitting signal)
  rsi_30_70:       REJECT (-2.23% vs baseline, worse OOS)
  rsi_40_60:       REJECT (-1.94% vs baseline, worse OOS)

Round 2: Stop/TP/weekday tests
  no_monday:       NEUTRAL (marginal across all metrics)
  stop_2atr:       NEUTRAL (test worse, validate better - inconsistent)
  tp_2atr:         REJECT (risk:reward math broken: 2 ATR TP / 3 ATR stop = unfavorable)

Round 3: Signal quality tests (first pass)
  volume_filter:   REJECT (high volume = momentum, not reversion - hypothesis was backwards)
  bb_width_1.2%:   REJECT (threshold miscalibrated - nearly no trades generated)
  no_friday:       NEUTRAL (consistently slight improvement, below 1% threshold)

Round 4: Signal quality tests (corrected)
  low_volume:      BORDERLINE ADOPT - see V2 below
  bb_width_0.7%:   REJECT (still only 16 trades, $148 avg win but insufficient sample)
  no_friday (r4):  NEUTRAL (consistent improvement, all periods positive)
```

### V2 (config/strategies/v2_low_volume.yaml) — CURRENT BEST CONFIG
- **Change:** Added max_volume_ratio: 0.9 (only trade low-volume BB extremes)
- **Rationale:** Allowed hours (13, 16, 21) have median volume ratio of 0.331x. High-volume bars
  at these hours = momentum/news events that DON'T revert. Low-volume = pure noise that snaps back.
  Calibration showed 74% of eligible-hour bars qualify (below 0.9x average).
- **Full backtest:** +10.54%, 50 trades, **56.0% WR**, **PF 2.29**, MaxDD **-1.59%**, Sharpe 0.26
- **Walk-forward:** Train +5.46% (PF 2.78), Test +3.52% (PF 2.18), Validate +0.10% (PF 1.10)
- **Targets met:** Return ✓, MaxDD ✓, WR ✓ (56% > 52% target), PF ✓ (2.29 > 1.5 target)
- **Note:** Validate period only 11 trades - small sample. Test period (20 trades) is stronger signal.
- **Candidate extension:** v2 + no_friday → 41T, 58.5% WR, PF 2.51, MaxDD -1.16%
  (validate improves to +0.31% but only 9 trades - not yet adopted)

### Key Learnings from Testing
1. **Only structural insights produce ADOPTs** - ATR filter (regime-based) worked; RSI/stop tweaks didn't
2. **High volume = momentum at quiet hours** - test confirmed opposite of naive hypothesis
3. **Validate period is noisy with <20 trades** - weight the test period (45 trades) more heavily
4. **Never change multiple parameters at once** - V2 original (5 changes) lost -9.01%
5. **No Monday/Friday matter little** - weekday effects below statistical significance
6. **tp_2atr confirmed**: Never set TP < SL without much higher win rate. 2 ATR TP / 3 ATR stop = requires 60%+ WR to break even.

---

### Trend Following Strategy (development/trend_following_v1.yaml)
- **Design:** Breakout of N-bar high/low, ADX > 20, high volume, elevated ATR
- **Complement:** Active when mean reversion isn't (ATR > 3.0, high volume, trending)
- **Full backtest (ES data):** +3.38%, 132 trades, 53.8% WR, PF 1.06, MaxDD -16.47%
- **Walk-forward:** Train -0.23%, Test -1.97%, Validate +0.80%
- **Status:** NOT VIABLE in current form. Positive full backtest but fails walk-forward.
  Needs: wider breakout period, better entry timing, or regime filter.

### EMA 9 Crossover Strategy (development/ema_crossover_*.yaml)
- **Design:** Trade when close crosses above/below EMA 9 on 5-min bars
- **Key risk:** Whipsaws - EMA crossovers happen on ~21% of all 5-min bars

Variants tested (ES data, 5 years):
```
Raw (v1):          5192 signals, 36.8% WR, PF 0.82, -93.6%  -> total loss
Filtered (v1_f):   1411 signals, 33.1% WR, PF 0.69, -96.0%  -> worse with basic filters
Strong (v2):        182 signals, 28.7% WR, PF 0.99,  -1.4%  -> near breakeven, peaked +37%
Balanced (v3):      248 signals, 32.7% WR, PF 0.98,  -3.5%  -> similar breakeven
```

Best variant (v2_strong) walk-forward:
  Train +9.11% (PF 1.53), Test +3.33% (PF 1.69), Validate -0.03% (PF 1.01)

**Status:** NOT PRODUCTION READY. Converges to PF ~1.0 regardless of filter tuning.
  The raw EMA 9 crossover on 5-min doesn't have structural edge on this data.
  Possible improvements to explore:
  - Dual EMA crossover (9/21) for fewer but stronger signals
  - EMA slope filter (only trade when EMA itself is trending)
  - Combine with market regime filter (only trade in trending regimes)
  - Different timeframe (15-min or 1-hour may reduce noise)

---

## Common Commands

```bash
# Run ALL production strategies at once (comparison table at the end)
python tools/run_all_production.py <data-file>

# Dashboard
python -m streamlit run dashboard.py

# Backtest (current best config = V2)
python src/backtest/run_backtest.py --config config/strategies/production/mean_rev_quiet_filter.yaml --data-file <file>

# Component test (runs all variants + walk-forward comparison)
python tools/component_test.py <data-file>

# Walk-forward test (single strategy)
python tools/walk_forward_test.py config/strategies/production/mean_rev_quiet_filter.yaml <data-file>

# Portfolio backtest (combine MR + TF with fixed weights)
python tools/portfolio_backtest.py <data-file>

# Portfolio backtest (regime-aware dynamic allocation)
python tools/portfolio_backtest.py <data-file> --regime

# Calibrate filter thresholds for new data period
python tools/calibrate_filters.py <data-file>

# Regime analysis
python tools/regime_analysis.py logs/trades_<timestamp>.csv <data-file>

# Download IB data
python src/ib/ib_integration.py --symbol MES --duration "1 Y" --bar-size "5 mins"
```

## Long-Term Strategy Development Roadmap

### Phase 1: Strategy diversification (DONE)
- Mean reversion (production - V2) + Trend following (development - 40-bar breakout)
- These are naturally complementary: MR works in ranging/low-vol, TF in trending/high-vol

### Phase 2: Portfolio infrastructure (DONE)
- Portfolio backtester combining multiple strategy equity curves
- Regime classifier (ATR percentile + ADX level -> 4 regimes)
- Dynamic allocation weights per regime
- Results: regime-weighted portfolio = +12.67%, Sharpe 0.81, MaxDD -5.59% on ES data
  vs TF alone: +12.96%, Sharpe 0.59, MaxDD -10.07% (44.5% drawdown reduction)

### Phase 3: Rolling walk-forward (DONE)
- tools/rolling_walk_forward.py: Slides train/test window across entire dataset
- Tests every 3-month period, not just the first year
- TF wide breakout: 7/18 windows profitable (39%), avg +0.65% per window
  Strong in trending periods (late 2021-early 2022), weak in ranging (2023)
  Confirms regime dependency -- expected for trend following
- MR on ES data: 0 signals (calibrated for MES price levels, needs real MES data)

### Phase 4: Risk management layer (DONE)
- src/risk/position_sizer.py: Standalone module with 4 functions:
  - half_kelly_size(): Position size from recent win rate and payoff ratio
  - drawdown_scaler(): Reduce position on drawdown (100%/50%/25%/0% at 0/5/10/15% DD)
  - confidence_score(): Rolling 0-100 score based on WR, PF, trend, consistency
  - portfolio_risk_check(): Cross-strategy correlation, concentration, simultaneous losses
- Ready to integrate into backtester when portfolio goes live

### Phase 5: Next steps (TODO)
- Test everything on real MES data (current ES data miscalibrates MR strategy)
- Integrate position_sizer into backtester for dynamic sizing during backtest
- Build auto-rebalancer: monthly rolling WF -> update config if params pass validation
- Forward test on paper account before live deployment

---

## Core Philosophy: Real Quant, Not Parameter Roulette

This document defines our systematic, statistically-backed approach to strategy development. We prioritize **finding real edge** over **chasing past performance**.

---

## The 3 Cardinal Rules

### 1. **TEST ONE THING AT A TIME**
- Never change multiple parameters simultaneously
- If V1 has 5 parameters and we want to improve it:
  - ❌ WRONG: Change all 5 at once, call it V2
  - ✅ RIGHT: Test V1 + param1 change, V1 + param2 change, etc.
- Only when we know WHICH change helps can we combine them

### 2. **VALIDATE OUT-OF-SAMPLE**
- Always hold out data we NEVER optimize on
- Walk-forward testing is mandatory, not optional
- If it only works on the training period, it's overfitting

### 3. **DEMAND STATISTICAL SIGNIFICANCE**
- Random chance can produce 10%+ returns with <100 trades
- Use confidence intervals, t-tests, Monte Carlo
- If we can't prove it's better than random, we don't trade it

---

## Our Systematic Workflow

### Phase 1: Understand (Before Any Optimization)

```
1. Walk-Forward Analysis
   ├─ Split data: Train (6mo) → Test (3mo) → Validate (3mo)
   ├─ Optimize ONLY on train period
   ├─ Validate on test period
   └─ Final check on validate period (touch ONCE)

2. Regime Analysis
   ├─ WHY did performance degrade?
   ├─ Chart equity vs ATR, volume, time-of-day
   ├─ Identify actual regime shifts
   └─ Build regime-adaptive logic, not hindsight parameters

3. Component Attribution
   ├─ Test each filter independently
   ├─ RSI filter alone: Does it add edge?
   ├─ Time filter alone: Does it add edge?
   ├─ Bollinger Bands alone: Does it add edge?
   └─ Only keep components that ADD value
```

### Phase 2: Build Robust Strategy

```
4. Parameter Sensitivity Analysis
   ├─ Monte Carlo: Test RSI 25-45 (random sampling)
   ├─ If profit only exists at RSI=35, it's curve-fitted
   ├─ Robust strategies work across parameter ranges
   └─ Example: "RSI 30-40 all profitable" = robust
              "Only RSI=35 works" = overfitting

5. Transaction Cost Stress Testing
   ├─ Double commissions: Still profitable?
   ├─ Add 1 tick slippage: Still profitable?
   ├─ Remove best 10 trades: Still profitable?
   └─ Fragile strategies fail stress tests

6. Cross-Asset Validation
   ├─ Does it work on ES (not just MES)?
   ├─ Does it work on NQ?
   ├─ Universal principles work across markets
   └─ Market-specific quirks are likely noise
```

### Phase 3: Statistical Validation

```
7. Bootstrap Confidence Intervals
   ├─ Resample trades 1000 times with replacement
   ├─ Calculate 95% CI on returns
   ├─ Example: "95% CI: 4% to 12%" = good
              "95% CI: -5% to 20%" = noise
   └─ Wide CIs mean we need more data

8. Risk-Adjusted Metrics
   ├─ Not just returns (survivorship bias)
   ├─ Sharpe Ratio > 1.0 (minimum)
   ├─ Calmar Ratio > 2.0 (return/max drawdown)
   ├─ Sortino Ratio (downside risk focus)
   └─ Max Adverse Excursion per trade

9. Reality Checks
   ├─ If strategy has 70% win rate, WHY?
   ├─ If Sharpe is 3.0, what's the catch?
   ├─ Exceptional results need exceptional explanations
   └─ "Too good to be true" usually is
```

---

## Red Flags: What NOT to Do

### ❌ Parameter Roulette
```
BAD: "V2 uses RSI 30/70, stops at 4.0 ATR, max 2 trades/day"
     → Changed 3 things, can't isolate what helped/hurt

GOOD: "V2 = V1 + wider stops only. Tests shows stops hurt performance."
     → Changed 1 thing, know exactly what it does
```

### ❌ Hindsight Optimization
```
BAD: "Strategy peaked at trade 89, so I optimized parameters for all trades"
     → Using future knowledge to optimize past

GOOD: "At trade 89, what market conditions changed? Build real-time detector."
     → Detecting regime shift as it happens
```

### ❌ Overfitting to Single Dataset
```
BAD: "Hours 13, 16, 21 are best. I'll only trade those."
     → Based on 1 year of data, could be noise

GOOD: "Hours 13, 16, 21 were best in train. Still best in test? Still best in validate?"
     → Validated across multiple periods
```

### ❌ Ignoring Statistical Significance
```
BAD: "V3 made 7.03% vs V1's 6.28%. V3 is better!"
     → 0.75% difference could be random

GOOD: "V3 made 7.03% vs V1's 6.28%. T-test p=0.43. Not statistically different."
     → Know when difference is meaningful
```

### ❌ Optimizing Too Many Parameters
```
BAD: Strategy with 15 parameters, all optimized on same dataset
     → Classic overfitting

GOOD: Strategy with 3-5 parameters, robust across ranges
     → Simple, robust, generalizable
```

---

## Our Current Strategy Development Rules

### Data Splits (12 months total: Feb 2025 - Feb 2026)
```
TRAIN:    Feb 2025 - Jul 2025 (6 months)
          └─ Optimize parameters here
          └─ Can iterate freely

TEST:     Aug 2025 - Oct 2025 (3 months)
          └─ Validate performance here
          └─ Can use to compare variants

VALIDATE: Nov 2025 - Feb 2026 (3 months)
          └─ FINAL check, use ONCE
          └─ If it fails here, strategy is bad
```

### Parameter Testing Protocol
```
1. Start with baseline (V1 current performance)
2. Test ONE change at a time:
   - V1_rsi30: Change RSI to 30/70, keep rest same
   - V1_stop4: Change stops to 4.0 ATR, keep rest same
   - V1_time: Change time filters, keep rest same
3. Compare each variant to baseline on TEST period
4. Only combine changes that INDEPENDENTLY improve
5. Final combined strategy gets ONE test on VALIDATE
```

### Acceptance Criteria (Before Going Live)
```
Strategy must pass ALL of these:

□ Sharpe Ratio > 1.0 on out-of-sample data
□ Win rate 45-55% (too high = suspicious)
□ Profit factor > 1.5 on out-of-sample
□ Max drawdown < 15%
□ Works across parameter ranges (sensitivity test)
□ Survives 2x commission stress test
□ 95% bootstrap CI doesn't include 0
□ At least 100 trades in validation period
□ No single trade accounts for >25% of profit
□ Strategy logic has clear economic rationale
```

---

## Documentation Requirements

Every strategy version MUST document:

```yaml
strategy_version: "adaptive_v4"
date: "2026-02-16"

hypothesis: "Mean reversion works in ranging markets with volatility filter"

changes_from_previous:
  - "Added volatility filter (ATR 2-8)"
  - "NO other changes from V1"

economic_rationale: "High ATR periods have more false breakouts, avoid them"

test_results:
  train_period: "2025-02-01 to 2025-07-31"
  train_return: "8.2%"
  train_sharpe: "1.3"

  test_period: "2025-08-01 to 2025-10-31"
  test_return: "7.1%"  # Slight degradation OK
  test_sharpe: "1.2"   # Maintained Sharpe

  statistical_significance:
    vs_baseline: "t-test p=0.03, significant"
    bootstrap_95ci: "4.2% to 10.1%"

decision: "APPROVED - deploy to validation period"
```

---

## Questions to Ask Before Each Change

1. **What is the hypothesis?**
   - "I think X will improve because Y"
   - Not: "Let me try X and see what happens"

2. **How will I test it?**
   - One change at a time
   - On which data period?
   - What metric defines success?

3. **What would disprove it?**
   - If returns improve but Sharpe degrades → not better
   - If only works in-sample → not real edge
   - If can't explain WHY it works → probably overfitting

4. **Is this curve-fitting or genuine insight?**
   - Curve-fitting: "Hour 13 was +2.1%, hour 16 was +0.8%"
   - Insight: "Morning hours after economic data are too volatile"

5. **Can I explain this to another quant?**
   - If logic requires hindsight, it's not tradeable
   - If logic is "because backtest said so," it's not robust

---

## Tools We Use

### Required for Every Analysis
- Walk-forward testing framework
- Bootstrap resampling for confidence intervals
- Parameter sensitivity scanner
- Regime detection analysis
- Trade attribution analysis

### Metrics We Track
- Returns (absolute and risk-adjusted)
- Sharpe, Sortino, Calmar ratios
- Win rate, profit factor, avg win/loss
- Max drawdown, max adverse excursion
- Trade distribution (no single outlier dominance)
- Parameter stability across time periods

---

## Final Reminder

**We are not trying to fit a curve to past data.**
**We are trying to find statistical edge that will persist.**

If we can't explain WHY something works, we don't trade it.
If it only works in-sample, we don't trade it.
If we can't prove it's better than random, we don't trade it.

---

*Last updated: 2026-02-17*
*Next review: After every major strategy revision*
