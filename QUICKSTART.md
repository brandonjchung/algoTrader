# Quick Start Guide

## Get Running in 10 Minutes

### 1. Install Python 3.11
- **Windows**: https://python.org/downloads/ (check "Add to PATH")
- **Mac**: `brew install python@3.11`
- **Linux**: `sudo apt install python3.11 python3-pip`

### 2. Set Up Environment

```bash
cd algoTrader

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Download Data

```bash
python src/data/data_downloader.py --start 2023-01-01 --end 2024-12-31 --interval 5m
```

### 4. Run Backtest

```bash
python src/backtest/run_backtest.py
```

### 5. Review Results

Check the `logs/` folder for:
- `trades_TIMESTAMP.csv` - Individual trades (open in Excel)
- `equity_curve_TIMESTAMP.csv` - Equity over time
- `backtest_TIMESTAMP.json` - Full results

## Understanding Results

**Good Metrics:**
- Sharpe Ratio > 1.5
- Profit Factor > 1.5
- Win Rate: 40-60%
- Max Drawdown < 20%

**Red Flags:**
- Win rate >80% (probably overfit)
- <30 total trades (not enough data)
- Profit factor <1.2 (too close to breakeven)

## Next Steps

1. Experiment with parameters in `config.yaml`
2. Test on different time periods
3. Understand every line of code
4. Build your own strategies
5. Paper trade for 2-3 months before going live

## Common Issues

**"Module not found"**
```bash
# Make sure venv is activated
pip install -r requirements.txt
```

**"No data found"**
```bash
# Download data first
python src/data/data_downloader.py --start 2023-01-01 --end 2024-12-31
```

Good luck! 🚀
