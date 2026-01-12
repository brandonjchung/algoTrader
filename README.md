# MES Algorithmic Trading System

A professional-grade backtesting and trading system for Micro E-mini S&P 500 (MES) futures.

## 🎯 Purpose

This system allows you to:
- Develop and test trading strategies with realistic market conditions
- Backtest against historical data with proper slippage and commissions
- Paper trade strategies before risking real capital
- Monitor performance with comprehensive analytics
- Build towards a systematic trading approach

## 📋 Prerequisites

### Python Installation

**Windows:**
1. Download Python 3.11 from https://www.python.org/downloads/
2. During installation, CHECK "Add Python to PATH"
3. Verify: Open Command Prompt, type `python --version`

**Mac:**
```bash
brew install python@3.11
```

**Linux:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

## 🚀 Quick Start

### 1. Clone This Repository

```bash
git clone https://github.com/brandonjchung/algoTrader.git
cd algoTrader
```

### 2. Set Up Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Settings

```bash
# Config file is ready to use with default settings
# Or customize parameters in config.yaml
```

### 5. Download Data

```bash
python src/data/data_downloader.py --symbol MES --start 2023-01-01 --end 2024-12-31 --interval 5m
```

### 6. Run Your First Backtest

```bash
python src/backtest/run_backtest.py
```

## 📁 Project Structure

```
algo-trading-system/
├── src/
│   ├── data/                 # Data collection and management
│   │   ├── data_downloader.py
│   │   └── data_cleaner.py
│   ├── strategies/           # Trading strategies
│   │   ├── base_strategy.py
│   │   └── volatility_breakout.py
│   ├── backtest/            # Backtesting engine
│   │   ├── backtester.py
│   │   └── run_backtest.py
│   ├── risk/                # Risk management
│   │   └── position_sizer.py
│   └── utils/               # Utilities and helpers
│       └── metrics.py
├── tests/                   # Unit tests
├── data/                    # Historical data storage
├── logs/                    # Backtest results and logs
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 📈 Key Metrics to Watch

- **Sharpe Ratio**: Risk-adjusted returns (aim for >1.5)
- **Maximum Drawdown**: Worst peak-to-trough loss (keep under 20%)
- **Profit Factor**: Gross profit / Gross loss (aim for >1.5)
- **Win Rate**: % winning trades (40-60% is normal)
- **Average Trade**: Should exceed costs significantly

## ⚠️ Critical Trading Rules

**Before Going Live:**
1. ✅ Backtest on at least 2 years of data
2. ✅ Paper trade for minimum 2-3 months
3. ✅ Strategy must survive multiple market conditions
4. ✅ Maximum 1-2% risk per trade
5. ✅ Have clear stop-loss rules
6. ✅ Set maximum daily/weekly loss limits
7. ✅ Never trade with money you can't afford to lose

**Red Flags (Don't Trade):**
- ❌ Strategy only works with specific parameters
- ❌ Win rate above 80% (usually overfit)
- ❌ No losing months in backtest (unrealistic)
- ❌ Doesn't account for slippage/commissions
- ❌ Uses future data (look-ahead bias)

## 📚 Resources

**Books:**
- "Advances in Financial Machine Learning" - Marcos López de Prado
- "Evidence-Based Technical Analysis" - David Aronson
- "Quantitative Trading" - Ernest Chan

**Communities:**
- r/algotrading (Reddit)
- QuantConnect Forums
- Elite Trader (Automated Trading section)

## 📝 License & Disclaimer

This software is for educational purposes only. Trading futures involves substantial risk of loss. Past performance does not guarantee future results. The authors assume no responsibility for your trading decisions or losses.

---

**Remember**: Your goal isn't to build the perfect system on day one. Your goal is to learn the process, understand what works and what doesn't, and gradually develop an edge through systematic testing and iteration.

Good luck, and trade smart! 🚀
