# Interactive Brokers Setup Guide - Step by Step

**Goal:** Connect to IB, download real MES data, validate winning strategy

**Time Required:** 30-45 minutes

---

## 📋 **WHAT YOU NEED**

✅ IB Paper Trading account (you have this!)
✅ IB account credentials (username/password)
✅ Computer with stable internet

---

## 🚀 **STEP 1: Download IB Gateway (5 min)**

**Option A: IB Gateway (RECOMMENDED - Lightweight)**
1. Go to: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
2. Download "Stable" version for your OS
3. Install (default settings are fine)

**Option B: Trader Workstation (TWS - Full featured)**
1. Go to: https://www.interactivebrokers.com/en/trading/tws.php
2. Download latest stable version
3. Install

**Which to choose?**
- Gateway: Lightweight, runs in background, perfect for algo trading
- TWS: Full trading platform, heavier, more features you don't need

**→ I recommend Gateway for algo trading**

---

## 🔧 **STEP 2: Configure IB Gateway (10 min)**

### **2a. Login**
1. Open IB Gateway
2. Username: Your IB paper trading username
3. Password: Your IB paper trading password
4. Trading Mode: **Paper Trading** (IMPORTANT!)
5. Click "Login"

### **2b. Enable API (CRITICAL)**

**In IB Gateway:**
1. Click **"Configure"** → **"Settings"**
2. Navigate to: **API → Settings**
3. Configure these settings:

```
✓ Enable ActiveX and Socket Clients: YES (check this!)
✓ Socket port: 7497
✓ Master API client ID: (leave blank or 0)
✓ Read-Only API: NO (uncheck this!)
✓ Download open orders on connection: YES
✓ Allow connections from localhost only: YES
```

4. Click "OK"

### **2c. Add Trusted IP**

Still in Settings → API:
1. Find "Trusted IPs" section
2. Add: `127.0.0.1`
3. Click "OK"

### **2d. Restart Gateway**
1. Close IB Gateway completely
2. Reopen and login again
3. This ensures settings take effect

---

## 🧪 **STEP 3: Test Connection (5 min)**

**Run this command:**
```bash
python src/ib/ib_integration.py --setup
```

This shows you the setup guide. Then test connection:

```bash
python src/ib/ib_integration.py
```

**Expected Output:**
```
Connecting to IB (attempt 1/3)...
  Host: 127.0.0.1
  Port: 7497 (Paper)
✅ Connected successfully!
   Server time: 2026-02-14 10:30:00
```

**If connection fails:**

### **Troubleshooting Connection Issues**

**Error: "Connection refused"**
- Solution: Make sure IB Gateway is running and logged in
- Check: Gateway window shows "Connected" status

**Error: "Socket port could not be opened"**
- Solution: Port 7497 is already in use
- Fix: Restart IB Gateway
- Or: Change port in Gateway settings, then use `--port 7496`

**Error: "Connection timeout"**
- Solution: Firewall blocking connection
- Fix (Linux): `sudo ufw allow 7497`
- Fix (Mac): System Preferences → Security → Allow

**Error: "API not enabled"**
- Solution: Go back to Step 2b
- Make sure "Enable ActiveX and Socket Clients" is checked
- Restart Gateway

---

## 📥 **STEP 4: Download Real MES Data (10-15 min)**

**Now download 5 years of REAL data:**

```bash
python src/ib/ib_integration.py --symbol MES --duration "5 Y" --bar-size "5 mins"
```

**What happens:**
1. Connects to IB
2. Finds nearest MES futures contract
3. Downloads 5 years of 5-minute bars
4. Saves to `data/historical/MES_5min_YYYY-MM-DD_to_YYYY-MM-DD_REAL.csv`

**Expected Output:**
```
Connecting to IB...
✅ Connected successfully!

Getting contract details for MES...
✅ Using contract: MESH26 (March 2026 expiry)

Downloading historical data...
  Duration: 5 Y
  Bar Size: 5 mins
  Regular Hours Only: True

✅ Downloaded 101,234 bars
   Date Range: 2021-02-14 to 2026-02-14
   Price Range: $3,245.50 to $6,123.75

✅ Saved to: data/historical/MES_5min_2021-02-14_to_2026-02-14_REAL.csv
   101,234 bars

📊 Account Summary:
  Net Liquidation: $1,000,000.00
  Available Funds: $999,000.00
  Buying Power: $4,000,000.00

✅ SUCCESS!
```

**Download Time:**
- Usually 5-15 minutes for 5 years of 5-min data
- IB limits data requests (be patient)
- Do NOT interrupt the download!

---

## ✅ **STEP 5: Verify Data Quality (2 min)**

```bash
# Check the file was created
ls -lh data/historical/*REAL.csv

# Preview first 10 rows
head -20 data/historical/MES_*_REAL.csv
```

**What to look for:**
- File size: Should be 10-50 MB (depending on years)
- Columns: timestamp, open, high, low, close, volume
- No missing bars (continuous timestamps)
- Prices look realistic (4,000-6,000 range for MES)

---

## 🔄 **STEP 6: Re-Run Winner on REAL Data (5 min)**

**Now test our winning strategy on REAL data:**

```bash
python src/backtest/run_backtest.py --config config_volatility_breakout_improved.yaml --data-file MES_*_REAL.csv
```

**This will:**
1. Load REAL MES data (not simulation!)
2. Run Improved Volatility Breakout strategy
3. Show if +219% return was realistic or lucky

**What to expect:**
- Return will likely be different (lower or higher)
- 150-250 trades is good
- Profit factor should still be >1.5
- Max drawdown should be <20%

**If results are within 20% of backtest → GREAT!**
**If results are dramatically different → Need to investigate**

---

## 🎯 **SUCCESS CRITERIA**

After completing these steps, you should have:

✅ IB Gateway running and connected
✅ API enabled and working
✅ 5 years of REAL MES data downloaded
✅ Winner strategy tested on real data
✅ Results validated (within reasonable range)

---

## 📝 **COMMON QUESTIONS**

### **Q: Paper or Live Trading?**
**A:** Always use Paper first!
- Port 7497 = Paper (safe, fake money)
- Port 7496 = Live (REAL money, dangerous!)
- Start with paper, test for 2-3 months

### **Q: How much data can I download?**
**A:** IB limits:
- 1 year of 1-min data
- 5 years of 5-min data
- 10 years of 1-hour data
- Unlimited daily data

### **Q: Does downloading cost money?**
**A:** No! Historical data is free for IB customers.

### **Q: Can I download ES instead of MES?**
**A:** Yes!
```bash
python src/ib/ib_integration.py --symbol ES
```
But MES is better for small accounts (1/10th size of ES)

### **Q: Connection keeps dropping?**
**A:**
- IB Gateway timeout setting is too short
- Settings → API → Auto-restart: 24 hours
- Or keep Gateway running 24/7

### **Q: "No market data" error?**
**A:**
- Need market data subscription for real-time
- Historical data works without subscription
- For paper trading, should work fine

---

## 🆘 **GETTING HELP**

**If stuck:**

1. **Check IB Gateway is running**
   - Should see Gateway window open
   - Status: "Connected"

2. **Check API is enabled**
   - Settings → API → "Enable ActiveX..." is checked
   - Port 7497 is set

3. **Check firewall**
   - Allow port 7497
   - Allow localhost connections

4. **Restart everything**
   - Close Gateway
   - Wait 10 seconds
   - Reopen and login
   - Try connection again

5. **Run with debug mode**
   ```bash
   python src/ib/ib_integration.py --port 7497 2>&1 | tee ib_debug.log
   ```
   This saves all output for debugging

---

## 🎉 **NEXT STEPS AFTER SUCCESS**

Once you have real data and verified results:

1. ✅ **Walk-forward testing** (I'll help with this)
2. ✅ **Set up monitoring dashboard** (Grafana)
3. ✅ **Build paper trading bot**
4. ✅ **Paper trade 2-3 months**
5. ✅ **Consider micro live trading**

---

## ⏱️ **TIMELINE**

**Today:**
- Download IB Gateway: 5 min
- Configure API: 10 min
- Test connection: 5 min
- Download data: 15 min
- Validate strategy: 5 min
- **Total: ~40 minutes**

**This Week:**
- Set up monitoring: 2-3 hours
- Build paper trading bot: 4-6 hours
- **Ready to paper trade!**

---

## 📞 **READY?**

**Start with Step 1 above, then:**

1. Download IB Gateway
2. Configure API settings
3. Test connection: `python src/ib/ib_integration.py`
4. Download data
5. Validate winner

**Let me know when you:**
- ✅ Have IB Gateway running
- ✅ Successfully connected (green checkmark)
- ✅ Downloaded MES data
- ❓ Need help with any step

**I'm here to help debug any issues!**

---

**Current Status:** Ready to begin
**Next Step:** Download IB Gateway (Step 1)

