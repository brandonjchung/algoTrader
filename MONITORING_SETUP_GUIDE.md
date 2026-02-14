# Monitoring Dashboard Setup Guide - Complete Infrastructure

**Goal:** Set up professional-grade monitoring for your automated trading bot

**Time Required:** 45-60 minutes

**Cost:** $0 (100% free using Docker + open source tools)

---

## 📋 **WHAT YOU NEED**

✅ Docker installed (free)
✅ 2GB free disk space
✅ Gmail account (for free email alerts)
✅ 15-30 minutes of setup time

---

## 🎯 **WHAT YOU GET**

After completing this guide, you'll have:

✅ **Real-time dashboard** showing:
- Live P&L and equity curve
- Win rate, profit factor, Sharpe ratio
- Open positions and current drawdown
- Trade frequency and performance metrics

✅ **Email alerts** for:
- Large losses (>1% of capital)
- Circuit breaker activation
- Daily performance summary
- System errors or disconnections

✅ **Historical data** stored for analysis:
- Every trade logged with full details
- Equity curve over time
- Performance metrics by hour/day/week/month

✅ **Professional monitoring stack:**
- Grafana: Beautiful dashboards (used by Netflix, Uber)
- InfluxDB: Time-series database (built for trading data)
- Python integration: Sends metrics from your bot

---

## 🚀 **STEP 1: Install Docker (10 min)**

### **Linux (Ubuntu/Debian):**
```bash
# Update package index
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (avoid sudo)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose -y

# Verify installation
docker --version
docker-compose --version
```

### **Mac:**
1. Download Docker Desktop: https://www.docker.com/products/docker-desktop
2. Install and open Docker Desktop
3. Verify: `docker --version` and `docker-compose --version`

### **Windows:**
1. Download Docker Desktop: https://www.docker.com/products/docker-desktop
2. Install (requires WSL2)
3. Open Docker Desktop
4. Verify in PowerShell: `docker --version`

**Important:** After installation, **log out and log back in** for group permissions to take effect.

---

## 🔧 **STEP 2: Deploy Monitoring Stack (5 min)**

### **2a. Create Directory Structure**
```bash
cd /home/user/algoTrader

# Create directories
mkdir -p monitoring/grafana monitoring/influxdb

# Set permissions
chmod -R 777 monitoring/
```

### **2b. Start Monitoring Stack**
```bash
# Start Grafana + InfluxDB
docker-compose up -d

# Verify containers are running
docker ps

# Expected output:
# CONTAINER ID   IMAGE                  STATUS
# abc123def456   grafana/grafana       Up 10 seconds
# def456ghi789   influxdb:2.7          Up 10 seconds
```

**What this does:**
- Starts Grafana on http://localhost:3000
- Starts InfluxDB on http://localhost:8086
- Both run in background (detached mode)
- Auto-restart if system reboots

### **2c. Check Logs (if issues)**
```bash
# Check Grafana logs
docker logs grafana

# Check InfluxDB logs
docker logs influxdb

# If errors, try:
docker-compose down
docker-compose up -d
```

---

## 📊 **STEP 3: Configure InfluxDB (10 min)**

### **3a. Open InfluxDB UI**
1. Open browser: http://localhost:8086
2. You'll see "Welcome to InfluxDB" screen

### **3b. Initial Setup**
```
Username: admin
Password: admin123456  (change this later!)
Organization: AlgoTrader
Bucket: trading_metrics
```

Click **"Configure Later"** for advanced settings.

### **3c. Create API Token**
1. Click **"Load Data"** → **"API Tokens"**
2. Click **"Generate API Token"** → **"All Access Token"**
3. Description: `Trading Bot Access`
4. Click **"Save"**
5. **COPY THE TOKEN** (you'll need this!)

**Example token:**
```
Kx9_xJ2zP9mY1qW3nL5vB8tR4hN7jF6sA0dC2eG5oI8uP1rT3kL9mN4wQ6xZ7yV
```

**⚠️ IMPORTANT:** Save this token somewhere safe. You can't see it again!

### **3d. Test Connection**
```bash
# Test InfluxDB is working
curl -X GET http://localhost:8086/health

# Expected output:
# {"name":"influxdb","message":"ready for queries and writes","status":"pass"}
```

---

## 📈 **STEP 4: Configure Grafana (10 min)**

### **4a. Login to Grafana**
1. Open browser: http://localhost:3000
2. Default credentials:
   - Username: `admin`
   - Password: `admin`
3. You'll be prompted to change password (do it!)

### **4b. Add InfluxDB Data Source**
1. Click **gear icon** (⚙️) → **"Data Sources"**
2. Click **"Add data source"**
3. Select **"InfluxDB"**
4. Configure:
   ```
   Name: TradingMetrics
   Query Language: Flux
   URL: http://influxdb:8086
   Organization: AlgoTrader
   Token: [paste your token from step 3c]
   Default Bucket: trading_metrics
   ```
5. Click **"Save & Test"**
6. Should see green ✅ "Data source is working"

**Troubleshooting:**
- If connection fails, use `http://localhost:8086` instead of `http://influxdb:8086`
- Make sure token is correct (no extra spaces)

### **4c. Import Pre-built Dashboard**
1. Click **"+"** icon → **"Import"**
2. Click **"Upload JSON file"**
3. Select: `config/grafana_dashboard.json`
4. Select data source: **"TradingMetrics"**
5. Click **"Import"**

**You should now see your dashboard!** (Empty initially, will populate when bot runs)

---

## 🔌 **STEP 5: Integrate With Trading Bot (10 min)**

### **5a. Install Python Dependencies**
```bash
pip install influxdb-client python-dotenv
```

### **5b. Configure Environment Variables**
Create `.env` file in project root:

```bash
cat > .env << 'EOF'
# InfluxDB Configuration
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=YOUR_TOKEN_HERE
INFLUXDB_ORG=AlgoTrader
INFLUXDB_BUCKET=trading_metrics

# Email Alerts Configuration
EMAIL_ENABLED=true
EMAIL_FROM=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_TO=your-email@gmail.com
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587

# Alert Thresholds
ALERT_LOSS_THRESHOLD_PCT=1.0
ALERT_CIRCUIT_BREAKER=true
ALERT_DAILY_SUMMARY=true
EOF
```

**Replace:**
- `YOUR_TOKEN_HERE` with your InfluxDB token from Step 3c
- `your-email@gmail.com` with your Gmail address
- `your-app-password` with Gmail app password (see Step 6)

### **5c. Test Metrics Writer**
```bash
# Test writing sample data to InfluxDB
python src/monitoring/metrics_writer.py --test

# Expected output:
# ✅ Connected to InfluxDB
# ✅ Wrote test metric
# ✅ Query successful: 1 point retrieved
```

### **5d. Verify in Grafana**
1. Go back to Grafana dashboard
2. Refresh (click refresh icon)
3. You should see test data point appear

---

## 📧 **STEP 6: Set Up Email Alerts (10 min)**

### **6a. Create Gmail App Password**
1. Go to: https://myaccount.google.com/security
2. Enable **2-Step Verification** (required)
3. Go to: https://myaccount.google.com/apppasswords
4. Select app: **"Mail"**
5. Select device: **"Other"** (enter: "Trading Bot")
6. Click **"Generate"**
7. **COPY THE 16-DIGIT PASSWORD** (e.g., `abcd efgh ijkl mnop`)

**⚠️ IMPORTANT:** This is NOT your regular Gmail password. It's a special app password.

### **6b. Update .env File**
```bash
# Edit .env file
nano .env

# Update these lines:
EMAIL_FROM=your-email@gmail.com
EMAIL_PASSWORD=abcdefghijklmnop  (16 chars, no spaces)
EMAIL_TO=your-email@gmail.com
```

### **6c. Test Email Alerts**
```bash
# Send test email
python src/monitoring/email_alerts.py --test

# Expected output:
# ✅ Connected to Gmail SMTP
# ✅ Test email sent successfully
# Check your inbox!
```

**Check your email** - you should receive a test alert.

**Troubleshooting:**
- If "Username and Password not accepted": Check app password (no spaces!)
- If "Less secure app": Use app password, not regular password
- If still failing: Disable 2FA temporarily, try, then re-enable

---

## ✅ **STEP 7: Verify Everything Works (5 min)**

### **7a. Run Quick Test**
```bash
# Run backtester with monitoring enabled
python src/backtest/run_backtest.py \
  --config config_volatility_breakout_improved.yaml \
  --enable-monitoring

# This will:
# 1. Run backtest
# 2. Send metrics to InfluxDB
# 3. Update Grafana dashboard
# 4. Send completion email
```

### **7b. Check Dashboard**
1. Open Grafana: http://localhost:3000
2. Navigate to **"Trading Bot Dashboard"**
3. You should see:
   - Total P&L graph
   - Win rate gauge
   - Recent trades table
   - Equity curve over time

### **7c. Check Email**
You should receive:
- **Backtest completion summary** with key metrics
- **Final P&L and statistics**

---

## 🎨 **DASHBOARD OVERVIEW**

Your Grafana dashboard includes:

### **Top Row - Key Metrics:**
- **Total P&L** (big number, green if positive)
- **Win Rate %** (gauge chart)
- **Profit Factor** (current vs target 2.0)
- **Max Drawdown %** (current vs limit 15%)
- **Open Positions** (live count)

### **Middle Row - Performance:**
- **Equity Curve** (line chart over time)
- **Daily P&L** (bar chart by day)
- **Trades Per Day** (frequency chart)
- **Win/Loss Distribution** (histogram)

### **Bottom Row - Details:**
- **Recent Trades Table** (last 50 trades)
- **Hourly Performance Heatmap** (best/worst hours)
- **Strategy State** (circuit breaker status, position)

### **Right Panel - Alerts:**
- **Active Alerts** (red if circuit breaker active)
- **System Status** (connection health)
- **Last Update Time** (data freshness)

---

## 🔔 **ALERT TYPES**

You'll receive emails for:

### **1. Large Loss Alert**
**Trigger:** Single trade loses >1% of capital
**Example:**
```
⚠️ LARGE LOSS ALERT
Trade: LONG MES @ 5,123.50
Loss: -$125.00 (-1.25%)
Time: 2026-02-14 10:30:00
Reason: Stop loss hit
```

### **2. Circuit Breaker Alert**
**Trigger:** 5 consecutive losses
**Example:**
```
🚨 CIRCUIT BREAKER ACTIVATED
Consecutive losses: 5
Total loss: -$287.50
Trading STOPPED until manual reset
Review recent trades before resuming.
```

### **3. Daily Summary**
**Trigger:** End of trading day (4:15 PM EST)
**Example:**
```
📊 DAILY TRADING SUMMARY - 2026-02-14

Trades: 3
Winners: 2 (66.7%)
Losers: 1 (33.3%)

P&L: +$156.25 (+1.56%)
Best Trade: +$87.50
Worst Trade: -$31.25

Equity: $10,156.25
Drawdown: -2.1%
```

### **4. System Error Alert**
**Trigger:** IB disconnection, data error, etc.
**Example:**
```
❌ SYSTEM ERROR
Error: Lost connection to IB Gateway
Time: 2026-02-14 14:23:45
Action: Attempting reconnection (retry 1/3)
```

---

## 🛠️ **MAINTENANCE & MANAGEMENT**

### **Daily Tasks (2-3 minutes):**
```bash
# Check dashboard
# Open: http://localhost:3000

# Check if containers are running
docker ps

# If stopped, restart:
docker-compose up -d
```

### **Weekly Tasks (5 minutes):**
```bash
# Check InfluxDB storage size
docker exec influxdb du -sh /var/lib/influxdb2

# View recent logs
docker logs --tail 100 grafana
docker logs --tail 100 influxdb

# Backup data (recommended!)
docker exec influxdb influx backup /tmp/backup
docker cp influxdb:/tmp/backup ./backups/$(date +%Y%m%d)
```

### **Stop Monitoring:**
```bash
# Stop containers (keeps data)
docker-compose down

# Start again later
docker-compose up -d
```

### **Complete Reset:**
```bash
# WARNING: This deletes ALL monitoring data!
docker-compose down -v
rm -rf monitoring/
# Then start from Step 2
```

---

## 📊 **DATA RETENTION**

### **Default Settings:**
- **InfluxDB:** Keeps all data forever (or until disk full)
- **Grafana:** Dashboards saved permanently

### **Configure Data Retention (Optional):**
```bash
# Keep only last 90 days of data
docker exec influxdb influx bucket update \
  --name trading_metrics \
  --retention 90d
```

### **Disk Usage:**
- **Per trade:** ~500 bytes
- **Per day (50 trades):** ~25 KB
- **Per year:** ~9 MB
- **5 years:** ~45 MB (negligible!)

---

## 🚨 **TROUBLESHOOTING**

### **Problem: "Cannot connect to InfluxDB"**
**Solution:**
```bash
# Check if InfluxDB container is running
docker ps | grep influxdb

# If not running:
docker-compose up -d influxdb

# Check logs
docker logs influxdb
```

### **Problem: "Grafana dashboard shows no data"**
**Solution:**
1. Check data source: Grafana → Configuration → Data Sources → Test
2. Verify InfluxDB has data:
   ```bash
   docker exec influxdb influx query 'from(bucket:"trading_metrics") |> range(start:-1h)'
   ```
3. Check time range in Grafana (top right) - try "Last 24 hours"

### **Problem: "Email alerts not working"**
**Solution:**
```bash
# Test email manually
python src/monitoring/email_alerts.py --test

# Common fixes:
# 1. Use Gmail app password (not regular password)
# 2. Enable 2FA on Google account
# 3. Check .env file has no typos
# 4. Try different SMTP port: 465 instead of 587
```

### **Problem: "Port already in use"**
**Solution:**
```bash
# Check what's using port 3000 or 8086
sudo lsof -i :3000
sudo lsof -i :8086

# Kill process (if safe)
sudo kill -9 <PID>

# Or change ports in docker-compose.yml
```

### **Problem: "Permission denied"**
**Solution:**
```bash
# Fix permissions
sudo chown -R $USER:$USER monitoring/
chmod -R 755 monitoring/

# Restart containers
docker-compose restart
```

---

## 🎯 **SUCCESS CRITERIA**

After completing this guide, you should have:

✅ Docker containers running (check: `docker ps`)
✅ InfluxDB accessible at http://localhost:8086
✅ Grafana accessible at http://localhost:3000
✅ Dashboard showing test data
✅ Email alerts working (received test email)
✅ Python scripts can write to InfluxDB
✅ .env file configured with secrets

---

## 🚀 **NEXT STEPS**

Now that monitoring is set up:

### **Phase 1: Integrate With Backtester (Done!)**
- Backtester already sends metrics to InfluxDB
- Run backtest with `--enable-monitoring` flag

### **Phase 2: Integrate With Paper Trading Bot (Week 5-6)**
- Paper trading bot will send live metrics
- Dashboard updates in real-time
- Alerts trigger during live trading

### **Phase 3: Add Custom Panels (Optional)**
- Create custom Grafana panels
- Add more metrics (Sharpe ratio over time, etc.)
- Set up SMS alerts (Twilio, costs $)

---

## 💰 **COST BREAKDOWN**

**Monthly Costs:**
- Docker: $0 (free)
- Grafana: $0 (free open source)
- InfluxDB: $0 (free open source)
- Gmail SMTP: $0 (free)
- Oracle Cloud (future): $0 (free tier)
- **Total: $0/month** 🎉

**Compare to Commercial Alternatives:**
- TradingView Pro: $15-60/month
- Datadog: $15-31/month
- MetricFire: $49-199/month
- **You're saving: $180-720/year!**

---

## 📞 **READY TO SET UP?**

**Start with Step 1 above, then:**

1. Install Docker (10 min)
2. Deploy monitoring stack (5 min)
3. Configure InfluxDB (10 min)
4. Configure Grafana (10 min)
5. Integrate with bot (10 min)
6. Set up email alerts (10 min)
7. Verify everything (5 min)

**Total time: ~60 minutes**

**Let me know when you:**
- ✅ Have Docker installed
- ✅ Containers running successfully
- ✅ Dashboard showing data
- ✅ Email alerts working
- ❓ Need help with any step

**I'm here to help debug any issues!**

---

**Current Status:** Ready to begin
**Next Step:** Install Docker (Step 1)
**Expected Time:** 60 minutes total
**Cost:** $0

