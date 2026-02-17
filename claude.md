# AlgoTrader Development Methodology

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

*Last updated: 2026-02-16*
*Next review: After every major strategy revision*
