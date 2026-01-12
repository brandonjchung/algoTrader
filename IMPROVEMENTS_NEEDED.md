# Backtesting System - Critical Improvements Needed

**Author:** Expert Review (10+ Years Algo Trading)
**Date:** 2026-01-12
**Status:** Pre-Production Review

---

## 🎯 Executive Summary

This backtesting system has a solid foundation but contains **critical bugs and design flaws** that will lead to significant discrepancies between backtested and live performance. Before using this system for real trading decisions, the following issues must be addressed.

**Risk Level:**
- 🔴 **CRITICAL (Must Fix):** 4 issues
- 🟡 **HIGH (Should Fix):** 6 issues
- 🟢 **MEDIUM (Nice to Have):** 5 issues

---

## 🔴 CRITICAL ISSUES (Must Fix Before Any Testing)

### 1. Entry Price Logic Error ⚠️
**File:** `src/strategies/volatility_breakout.py:112-113, 122-123`

**Current Code:**
```python
if is_contracted and current_close > rolling_high:
    df.loc[df.index[i], 'signal'] = 1
    df.loc[df.index[i], 'entry_price'] = rolling_high  # WRONG!
```

**Problem:**
- You detect breakout when `close > rolling_high`
- But you set entry price to `rolling_high` (the breakout level)
- In reality, if close is already above the high, you can't enter AT the high
- You'd enter at next bar's open, or use a limit order (which might not fill)

**Impact:**
- Backtest shows unrealistically good fills
- Live trading will have 0.5-2 point worse entry (on MES at 4500, that's $2.50-$10 per contract)
- Over 100 trades, could be $250-$1000 difference

**Fix Options:**
1. Enter at next bar's open (realistic for market orders)
2. Enter at current close (if assuming you can act instantly)
3. Add breakout_buffer (e.g., enter at high + 0.5 ATR to confirm strength)

**Recommended Fix:**
```python
# Option 1: Next bar open (most realistic)
df.loc[df.index[i], 'entry_price'] = df.iloc[i+1]['open'] if i+1 < len(df) else current_close

# Option 2: Current close (acceptable for 5-min bars)
df.loc[df.index[i], 'entry_price'] = current_close

# Option 3: Stop order above high (best practice)
df.loc[df.index[i], 'entry_price'] = rolling_high + (breakout_buffer * current_atr)
```

---

### 2. Slippage Calculation Error ⚠️
**File:** `src/backtest/backtester.py:119-126`

**Current Code:**
```python
def calculate_slippage(self, entry_price: float, direction: int) -> float:
    slippage_amount = self.slippage_ticks * self.tick_value  # WRONG!
    return entry_price + slippage_amount if direction == 1 else entry_price - slippage_amount
```

**Problem:**
- `tick_value` = $1.25 (dollar value per tick)
- `tick_size` = 0.25 (point value per tick)
- Should be: `slippage_ticks * tick_size` = 1 * 0.25 = 0.25 points
- Currently: `slippage_ticks * tick_value` = 1 * 1.25 = 1.25 points (5x too much!)

**Impact:**
- Overstating slippage by 5x
- Makes profitable strategies look unprofitable
- $1.25 slippage per entry + exit = $2.50 per round trip (should be $0.50)
- Over 100 trades: $250 error (vs $50 actual)

**Fix:**
```python
def calculate_slippage(self, entry_price: float, direction: int) -> float:
    slippage_in_points = self.slippage_ticks * self.tick_size  # FIXED
    return entry_price + slippage_in_points if direction == 1 else entry_price - slippage_in_points
```

---

### 3. Time Filters Not Enforced ⚠️
**Files:** `config.yaml` has filters, but `volatility_breakout.py` never checks them

**Current Code:**
```python
# Config says:
time_filters:
  avoid_first_minutes: 15
  avoid_last_minutes: 15

# But generate_signals() never calls is_market_hours() or checks these filters!
```

**Problem:**
- BaseStrategy has `is_market_hours()` method
- VolatilityBreakoutStrategy never uses it
- Will trade during market open/close when spreads are wide and slippage is high

**Impact:**
- Taking trades during worst liquidity periods
- Open: 9:30-9:45 AM has wide spreads, panic moves, false breakouts
- Close: 3:45-4:00 PM has position squaring, not genuine moves
- Estimated 20-30% of signals might be in these windows

**Fix:**
```python
# In generate_signals(), before checking breakout:
if not self.is_market_hours(current_bar.name):
    continue
```

---

### 4. Position Sizing Doesn't Use Risk %
**File:** `backtester.py:223-231` and config

**Current Code:**
```python
# Config says:
risk:
  max_risk_per_trade_pct: 1.0  # Risk 1% per trade

# But code does:
size=1  # Fixed 1 contract, regardless of stop distance
```

**Problem:**
- With 2.0x ATR stop and ATR at 10 points, you're risking 20 points = $100 on $10,000 = 1.0% ✓
- But if ATR rises to 20 points, you're risking 40 points = $200 = 2.0% ✗
- Risk per trade varies wildly based on volatility

**Impact:**
- Inconsistent risk-taking
- Could blow through daily loss limits in high volatility
- Not properly scaling with account size

**Fix:**
```python
# Calculate position size based on risk %
account_risk_dollars = self.equity * (self.config['risk']['max_risk_per_trade_pct'] / 100)
stop_distance_points = abs(entry_price - stop_loss)
stop_distance_dollars = stop_distance_points * self.point_value
position_size = int(account_risk_dollars / stop_distance_dollars)
position_size = max(1, min(position_size, max_position_limit))  # Floor at 1, cap at limit
```

---

## 🟡 HIGH PRIORITY ISSUES (Should Fix Before Production)

### 5. No Volume Filter
**Impact:** Breakouts without volume confirmation fail 60-70% of the time

**Fix:**
```python
# In calculate_indicators():
df['volume_ma'] = df['volume'].rolling(window=20).mean()
df['volume_ratio'] = df['volume'] / df['volume_ma']

# In generate_signals():
if current_bar['volume_ratio'] < 1.2:  # Volume must be 20% above average
    continue
```

---

### 6. No Trend Filter
**Impact:** Trading counter-trend breakouts is low probability

**Fix:**
```python
# In calculate_indicators():
df['ema_50'] = self.calculate_ema(df, 50)
df['ema_200'] = self.calculate_ema(df, 200)
df['trend'] = np.where(df['ema_50'] > df['ema_200'], 1, -1)

# In generate_signals():
# Only take LONG breakouts in uptrend, SHORT in downtrend
if signal == 1 and current_bar['trend'] != 1:
    continue
if signal == -1 and current_bar['trend'] != -1:
    continue
```

---

### 7. Entry Timing Problem (Hindsight Bias)
**Impact:** Looking at current bar's close creates unrealistic entry assumptions

**Current Logic:**
```python
# At bar i, you check if current_close > rolling_high
# Then enter at rolling_high
# But you couldn't know the close until AFTER the bar ended
```

**Fix:** Either:
1. Use previous bar's close to detect breakout, enter next bar
2. Use stop orders and enter when high is exceeded (need tick data)
3. Enter at next bar's open (conservative)

---

### 8. Volatility Contraction Threshold Too Loose
**Current:** `threshold: 0.7` (ATR just needs to be 30% below average)

**Problem:** Not selective enough, will get many false signals

**Recommendation:** Use `0.5` or `0.6` for tighter consolidation detection

---

### 9. No Breakout Strength Validation
**Current:** Any close above high triggers signal

**Improvement:** Measure breakout strength
```python
breakout_strength = (current_close - rolling_high) / current_atr
if breakout_strength < 0.25:  # Must break by at least 25% of ATR
    continue
```

---

### 10. Daily Loss Limit Uses Wrong Equity Base
**File:** `backtester.py:132-142`

**Current Code:**
```python
todays_pnl_pct = (todays_pnl / self.equity) * 100  # Uses CURRENT equity
```

**Problem:** Should use start-of-day equity, not current equity

**Fix:**
```python
# Track start of day equity
if current_date != self.current_day:
    self.start_of_day_equity = self.equity
    self.current_day = current_date

todays_pnl_pct = (todays_pnl / self.start_of_day_equity) * 100
```

---

## 🟢 MEDIUM PRIORITY ISSUES (Nice to Have)

### 11. Sharpe Ratio Calculation Assumes Daily Returns
**File:** `backtester.py:288-292`

Uses bar-level returns but multiplies by √252 (assumes daily data)

**Fix:** Use `√(252 * bars_per_day)` where `bars_per_day = 78` for 5-min bars

---

### 12. No Data Quality Validation
Missing checks for:
- Price gaps > 5 ATR (likely bad data)
- Volume = 0 bars
- Duplicate timestamps
- Missing bars (should be continuous)

---

### 13. Bars Held Calculation Hardcoded
**File:** `backtester.py:70`

```python
self.bars_held = (exit_time - entry_time).total_seconds() / 60 / 5  # Assumes 5-min bars
```

Should read timeframe from config.

---

### 14. No Walk-Forward Testing
**Current:** Option in config but not implemented

**Recommendation:** Implement walk-forward:
- Train on 6 months, test on 1 month
- Roll forward monthly
- Prevents overfitting

---

### 15. Missing Key Metrics
Add these to `calculate_metrics()`:
- `consecutive_wins` / `consecutive_losses` (max streaks)
- `largest_win` / `largest_loss`
- `profit_per_bar_held` (efficiency metric)
- `monthly_returns` (breakdown by month)
- `win_rate_long` vs `win_rate_short` (directional bias)
- `average_mae_to_stop_ratio` (how often you hit stops vs worse)

---

## 🎯 Recommended Priority Order

### Phase 1: Critical Fixes (Do These First)
1. Fix entry price logic (Issue #1)
2. Fix slippage calculation (Issue #2)
3. Enforce time filters (Issue #3)
4. Implement proper position sizing (Issue #4)

### Phase 2: Strategy Improvements
5. Add volume filter (Issue #5)
6. Add trend filter (Issue #6)
7. Fix entry timing (Issue #7)
8. Tighten volatility threshold (Issue #8)
9. Add breakout strength filter (Issue #9)

### Phase 3: Risk & Metrics
10. Fix daily loss calculation (Issue #10)
11. Add missing metrics (Issue #15)
12. Implement data validation (Issue #12)

### Phase 4: Advanced
13. Walk-forward testing (Issue #14)
14. Fix Sharpe calculation (Issue #11)
15. Dynamic bars calculation (Issue #13)

---

## 📚 Learning Resources for New Traders

Since you're 1 year in, here are concepts to study:

1. **Entry Timing & Execution**
   - Stop orders vs Limit orders
   - Market-on-close vs Market-on-open
   - Fill simulation accuracy

2. **Breakout Trading Fundamentals**
   - Volume confirmation (read: "How to Day Trade for a Living" - Aziz)
   - False breakout patterns
   - Consolidation patterns (triangles, flags, rectangles)

3. **Risk Management**
   - Kelly Criterion for position sizing
   - Volatility-adjusted position sizing
   - Correlation risk (don't trade 5 S&P strategies at once)

4. **Backtesting Pitfalls**
   - Survivorship bias
   - Look-ahead bias (using future information)
   - Over-optimization (curve fitting)
   - Out-of-sample testing

5. **Books to Read:**
   - "Evidence-Based Technical Analysis" by David Aronson
   - "Quantitative Trading" by Ernest Chan
   - "Trading Systems" by Emilio Tomasini

---

## 🧪 Testing Protocol

Once fixes are made:

1. **Data Requirements:**
   - Minimum 2 years of data
   - Include different market regimes (trending, choppy, high vol, low vol)
   - 2023-2024 is good (has bull run + corrections)

2. **Validation Steps:**
   - Run backtest on full period
   - Check total trades > 30 (minimum for statistical significance)
   - Win rate should be 40-60% (realistic)
   - Profit factor > 1.5 (sustainable)
   - Max drawdown < 20% (acceptable)
   - Sharpe > 1.0 (good), > 1.5 (excellent)

3. **Red Flags:**
   - Win rate > 70% (likely overfit or lookahead bias)
   - Profit factor > 3.0 (too good to be true)
   - Only 1-2 losing months (unrealistic)
   - All winners or all losers in a row (check logic)

4. **Next Steps:**
   - Paper trade for 2-3 months minimum
   - Track differences between backtest and live (slippage, fills, etc.)
   - Start with 1 contract only
   - Never risk more than 1% per trade
   - Keep a trading journal

---

## ⚠️ FINAL WARNING

**DO NOT TRADE LIVE UNTIL:**
- All critical bugs are fixed (Phase 1)
- You've backtested on 2+ years of data
- You've paper traded for 2-3 months
- You understand every line of code
- You can explain why each trade was taken
- You've stress-tested the strategy in different market conditions

Remember: **"Backtesting is not predictive, it's educational."**

The goal is to learn if your edge has a CHANCE of working, not to predict future returns.

---

## 📊 Expected Realistic Performance (After Fixes)

For a breakout strategy on MES with proper filters:

**Realistic Targets:**
- Win Rate: 45-55%
- Profit Factor: 1.3 - 1.8
- Sharpe Ratio: 0.8 - 1.5
- Max Drawdown: 12-18%
- Annual Return: 15-35% (on capital, not account)

**Warning Signs:**
- Win rate < 35% (strategy might be fundamentally flawed)
- Profit factor < 1.2 (not worth the risk)
- Sharpe < 0.5 (better off in index funds)
- Max drawdown > 25% (too much pain)

---

**Good luck, and remember: The goal is to survive long enough to learn, not to get rich quick!**
