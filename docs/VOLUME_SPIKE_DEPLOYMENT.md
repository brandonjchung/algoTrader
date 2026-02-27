# Volume Spike Reversal - Production Deployment Guide

## Strategy Overview

**Volume Spike Reversal** is a counter-trend strategy that fades climax moves with volume exhaustion signals.

### Core Logic
- When price breaks Bollinger Bands during a **4x volume spike**, it signals exhaustion
- Counter-trend entry: Buy climax sells, sell climax buys
- Exit via stop loss (2.0 ATR) or take profit (3.5 ATR)

### Backtest Performance (Nov 2025 - Feb 2026, 3 months)
- **Return**: +11.23%
- **Win Rate**: 61.90%
- **Profit Factor**: 3.20
- **Max Drawdown**: -0.87%
- **Trades**: 42 (~3 per week)
- **Avg Trade**: $26.75

### Optimized Parameters (Combo #132)
```yaml
volume_spike_threshold: 4.0    # Only trade 4x volume spikes
bb_std_mult: 2.0               # Standard Bollinger Bands
stop_loss_atr_multiple: 2.0    # 2x ATR stop (gives room to breathe)
take_profit_atr_multiple: 3.5  # 3.5x ATR target (let winners run)
```

**Why these parameters:**
- Based on sensitivity analysis across 144 combinations
- Chosen for robustness (parameter averages) not cherry-picking
- `stop=2.0 ATR` shows 59.79% avg WR vs 46.67% at 1.0 ATR
- `target=3.5 ATR` shows 9.29% avg return vs 4.55% at 2.0 ATR

---

## Deployment Steps

### Step 1: Forward Testing (CRITICAL - Do First)

**Why:** The strategy was optimized on Nov 2025 - Feb 2026 data. You MUST validate it works on NEW, unseen data before risking real money.

**How:**
```bash
# 1. Download fresh MES data for a NEW period (e.g., March - May 2026)
python tools/download_ib_data_paper.py

# 2. Run forward test on the fresh data
python tools/forward_test_volume_spike.py --data-file data/historical/MES_NEW_PERIOD.csv

# 3. Check results:
#    - Return should be at least 5-6% (50% of backtest)
#    - Win Rate should be 50%+
#    - Profit Factor should be 1.5+
#    - Max Drawdown should be < 2%
```

**If forward test fails:**
- ❌ Strategy may be overfitted
- ❌ Market regime may have changed
- ❌ Do NOT deploy to live trading
- ✅ Collect more data and re-evaluate

**If forward test passes:**
- ✅ Proceed to Step 2

---

### Step 2: Paper Trading (1-2 months)

**Why:** Validate live execution, slippage, and real-time signal generation.

**Setup:**
1. Ensure IB Gateway/TWS is running with paper account
2. Enable API access (port 7497 for paper)
3. Review production config: `config/strategies/production/volume_spike_reversal.yaml`

**Run (Manual for now):**
```bash
python tools/run_volume_spike_live.py --mode paper
```

**What to monitor:**
- Are signals generating correctly in real-time?
- Is execution slippage within expectations? (1 tick = $1.25)
- Are stop losses and take profits working correctly?
- Does performance match forward test results?

**Paper trading checklist:**
- [ ] Run for at least 1-2 months
- [ ] Get at least 20-30 trades
- [ ] Win rate stays above 50%
- [ ] Profit factor stays above 1.5
- [ ] No execution issues (fills, slippage, disconnections)

---

### Step 3: Live Trading (Start Small)

**⚠️ WARNING: REAL MONEY AT RISK**

**Prerequisites:**
- ✅ Forward test passed
- ✅ Paper trading successful for 1-2 months
- ✅ All execution issues resolved
- ✅ Risk management verified

**Start small:**
- Begin with 1 MES contract (micro futures)
- Risk per trade: ~$30-50 (2 ATR stop on MES = ~6-10 points = $30-50)
- Max daily loss: Set to $100-150
- Monitor EVERY trade for first month

**Run:**
```bash
python tools/run_volume_spike_live.py --mode live
```

**Monitor daily:**
- Trade execution quality
- Win rate, PF, drawdown vs expectations
- Market regime changes (is it still fading breakouts?)

**Scale up only if:**
- Performance matches expectations for 1+ month
- Win rate > 55%, PF > 2.0
- You're comfortable with the execution

---

## Risk Management

### Position Sizing
- **Current**: 1 MES contract
- **Risk per trade**: ~2 ATR stop = $30-50
- **Account size**: Start with $10,000+ (allows for drawdowns)

### Circuit Breakers
- **Max consecutive losses**: 5 (built into config)
- **Max daily loss**: 2% of capital (built into config)
- **Max drawdown**: 15% of capital (built into config)

### When to STOP Trading
- ❌ Win rate drops below 45% over 20+ trades
- ❌ Profit factor drops below 1.2
- ❌ Max drawdown exceeds -3%
- ❌ Market regime clearly changes (breakouts start working)

---

## Market Regime Considerations

**When Volume Spike works well:**
- ✅ Ranging, choppy markets
- ✅ Mean-reverting conditions
- ✅ Breakouts consistently fail

**When it may struggle:**
- ❌ Strong trending markets
- ❌ Low volatility (volume spikes rare)
- ❌ Breakouts start working (regime shift)

**Regime monitoring:**
- Track ADX: If consistently > 25, market is trending (strategy may struggle)
- Track win rate: If drops to 40-45%, consider pausing
- Visual check: Are breakouts starting to work? If yes, pause strategy

---

## Files Reference

### Configuration
- `config/strategies/production/volume_spike_reversal.yaml` - Production parameters

### Tools
- `tools/forward_test_volume_spike.py` - Test on fresh data
- `tools/run_volume_spike_live.py` - Live/paper trading runner (skeleton)
- `tools/compare_production_strategies.py` - Compare multiple strategies
- `tools/optimize_volume_spike.py` - Re-optimize if needed

### Strategy Code
- `src/strategies/volume_spike_reversal_strategy.py` - Main strategy logic

---

## Next Steps

1. **Immediate**: Run forward test on fresh data (March 2026+)
2. **If passed**: Set up paper trading for 1-2 months
3. **If successful**: Begin live trading with 1 contract
4. **Monitor**: Track performance daily for first month

---

## Questions?

- Strategy underperforming? Check if market regime changed
- Execution issues? Review slippage settings and IB connection
- Need to re-optimize? Use `tools/optimize_volume_spike.py` on fresh data

Remember: **This strategy was optimized on 3 months of data.** It needs validation on fresh data before risking real money. Start conservative, scale slowly.
