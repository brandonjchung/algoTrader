# Infrastructure Plan: Production-Ready Algo Trading System

**Goal:** Automated, monitored, safe trading system that runs 24/7
**Your Requirements:**
- Free or cheap hosting
- Robust error handling
- Daily check-ins (not constant alerts)
- Safety against overtrading, margin issues, accidents

---

## 1. LIVE MONITORING - How to Run Unattended

### What "Unattended" Actually Means:

**NOT:**
❌ Set it and forget it forever
❌ Zero human oversight
❌ Runs perfectly with no issues

**ACTUALLY:**
✅ Runs 24/7 without you watching
✅ Handles errors gracefully (doesn't crash)
✅ Sends alerts on critical issues
✅ You check dashboard once daily (5-10 min)

---

### Components Needed:

#### A. **Process Manager** (Keeps System Running)

**Tool:** `systemd` (Linux) or `supervisor` or `PM2`

**What it does:**
- Starts your trading bot on server boot
- Restarts if it crashes
- Logs all output
- Runs in background 24/7

**Example Setup:**
```bash
# systemd service file
[Unit]
Description=MES Trading Bot
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/algoTrader
ExecStart=/usr/bin/python3 src/live/trading_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Cost:** FREE

---

#### B. **Health Monitoring Dashboard**

**Options:**

##### Option 1: Simple Log File + Cron Job (FREE)
```python
# Daily status email
# Cron: 0 8 * * * /home/trader/send_daily_report.sh

import smtplib
from email.mime.text import MIMEText

# Read today's trades
# Calculate P&L
# Send email with summary
```

**Pros:** Free, simple
**Cons:** Basic, manual checking

---

##### Option 2: Grafana + InfluxDB (FREE, Better)

**What it is:**
- Real-time dashboard in web browser
- Charts of equity, trades, metrics
- Can check from phone/laptop anytime
- Alerts on thresholds

**Setup:**
1. InfluxDB stores metrics (time-series database)
2. Grafana displays charts (web dashboard)
3. Your bot writes metrics to InfluxDB
4. You view Grafana from anywhere

**Example Metrics:**
- Current equity
- Open positions
- Today's P&L
- Win rate (rolling 7 days)
- Current drawdown
- Last trade time

**Cost:** FREE (self-hosted)

---

##### Option 3: Hosted Monitoring (Paid, Easiest)

**Services:**
- **Datadog** - $15/month (monitoring + logs)
- **New Relic** - $0-25/month (free tier available)
- **Grafana Cloud** - Free tier available

**Pros:** Zero setup, professional
**Cons:** Costs money

---

#### C. **Alerting System** (Critical Events Only)

**When to Alert:**

| Event | Alert Method | Urgency |
|-------|-------------|---------|
| Daily summary | Email | Low |
| System crash | SMS + Email | HIGH |
| Drawdown > 10% | Email | Medium |
| Drawdown > 15% | SMS | HIGH |
| Position stuck open | Email (after 2 hours) | Medium |
| Cannot connect to broker | SMS | HIGH |
| 5 consecutive losses | Email | Medium |
| Margin call risk | SMS | CRITICAL |

**Tools:**

**Email:** SMTP (Gmail, SendGrid free tier)
**SMS:** Twilio ($0.0075/SMS, ~$20/month for daily use)
**Push Notification:** Pushover ($5 one-time)

**My Recommendation:**
- Daily email summary (automated)
- SMS only for critical (crash, margin, cannot connect)

**Cost:** $5-20/month

---

### Daily Check-In Workflow (5-10 min):

**Morning Routine:**
1. Check email: Daily summary report
   - Yesterday's trades
   - Current equity
   - Open positions
   - Any alerts

2. Open Grafana dashboard (2 min)
   - Glance at equity chart
   - Check if system is running
   - Verify last trade timestamp

3. Spot check (if needed)
   - Log into IB to verify positions match
   - Check logs if anything unusual

**That's it!** No constant monitoring needed.

---

## 2. INFRASTRUCTURE - Server, Database, Error Handling

### A. **Server Hosting (Free/Cheap Options)**

#### Option 1: **Oracle Cloud Free Tier** (RECOMMENDED) ⭐

**What you get:**
- 2 AMD VMs (free forever)
- 200 GB storage
- 10 TB bandwidth/month
- Located close to NYSE (low latency)

**Specs per VM:**
- 1 GB RAM
- 1 OCPU (1/8 of CPU)
- Enough for algo trading

**Pros:**
- Actually free (not trial)
- Good uptime
- Low latency to exchanges

**Cons:**
- Slightly complex setup
- Oracle UI is clunky

**Cost:** $0/month

---

#### Option 2: **AWS EC2 Free Tier** (12 Months Free)

**What you get:**
- t2.micro instance (1 year free)
- 750 hours/month (24/7 for 1 instance)
- 30 GB storage

**After 1 year:** ~$8-10/month

**Pros:**
- Easy setup
- Great documentation
- Very reliable

**Cons:**
- Costs money after year 1
- Can get expensive if you're not careful

**Cost:** $0 first year, $8-10/month after

---

#### Option 3: **Home Raspberry Pi** (One-Time $50)

**What it is:**
- Raspberry Pi 4 (8GB RAM)
- Runs Linux
- Sits in your home
- Always on

**Pros:**
- Cheap one-time cost ($50-80)
- Full control
- No monthly fees

**Cons:**
- Depends on home internet
- Power outage = downtime
- Need to set up yourself

**Cost:** $50-80 one-time

---

#### Option 4: **DigitalOcean Droplet** (Paid, Reliable)

**Specs:**
- Basic droplet: $6/month
- 1 GB RAM, 1 CPU
- Backups available (+$1.20/month)

**Pros:**
- Simple setup
- Reliable
- Good for beginners

**Cons:**
- Costs money

**Cost:** $6-12/month

---

### My Recommendation:

**Start:** Oracle Cloud Free Tier
**If Oracle is too complex:** AWS Free Tier → then switch to DigitalOcean after year

**Location:** Choose datacenter in **US-East** (closest to NYSE)

---

### B. **Database - Do You Need One?**

**Short Answer:** Not immediately, but yes for production.

#### What Database Is For:

| Data | Storage Method | Why Database Better |
|------|---------------|---------------------|
| **Historical OHLCV** | CSV files | ✅ CSV is fine |
| **Backtest results** | JSON files | ✅ JSON is fine |
| **Live trades** | CSV files | ❌ Risky! Use database |
| **Real-time metrics** | In-memory | ❌ Lost on crash! Use database |
| **System logs** | Log files | ✅ Files are fine |
| **Daily P&L** | CSV files | ❌ Use database for querying |

---

#### Database Options:

##### Option 1: **SQLite** (Start Here) ⭐

**What it is:** File-based database (no server needed)

**Pros:**
- Zero setup
- Built into Python
- Fast enough for <10,000 trades/day
- Easy to backup (copy one file)

**Cons:**
- Not great for concurrent writes
- Limited analytics capabilities

**Use for:**
- Live trade logging
- System state
- Daily metrics

**Cost:** FREE

**Example:**
```python
import sqlite3

# Create database
conn = sqlite3.connect('trading.db')

# Log trade
cursor.execute("""
    INSERT INTO trades (timestamp, symbol, direction, entry, size)
    VALUES (?, ?, ?, ?, ?)
""", (datetime.now(), 'MES', 'LONG', 4550.0, 1))

conn.commit()
```

---

##### Option 2: **PostgreSQL** (Later, If Needed)

**When to upgrade:**
- More than 10,000 trades total
- Need complex analytics
- Running multiple strategies
- Want advanced querying

**Hosting:**
- Self-hosted (free)
- ElephantSQL (free tier: 20 MB)
- Render (free tier available)

**Cost:** $0-15/month

---

##### Option 3: **InfluxDB** (For Time-Series Metrics) ⭐

**What it's for:**
- Real-time metrics (equity, positions, etc.)
- NOT for trade logs
- Works with Grafana

**Use case:**
- Store equity every minute
- Store RSI, ATR values
- Monitor system health

**Cost:** FREE (self-hosted)

---

### My Recommendation:

**Phase 1 (Now - 3 months):**
- SQLite for trade logging
- CSV for historical data
- JSON for backtest results

**Phase 2 (3-6 months):**
- Keep SQLite for trades
- Add InfluxDB for metrics
- Keep CSV/JSON

**Phase 3 (6+ months, if scaling):**
- Upgrade to PostgreSQL if needed
- Keep InfluxDB for metrics

---

### C. **Robust Error Handling** (CRITICAL)

This is where most retail algo traders fail. You want **bulletproof** code.

---

#### Error Handling Principles:

##### 1. **Fail Gracefully, Never Crash**

**Bad:**
```python
# This crashes the whole system
price = broker.get_price('MES')
if price > 4500:
    buy()
```

**Good:**
```python
try:
    price = broker.get_price('MES')
    if price is None:
        logger.warning("Price is None, skipping this bar")
        return

    if price > 4500:
        try:
            buy()
        except BrokerError as e:
            logger.error(f"Failed to buy: {e}")
            alert_admin("Order failed", str(e))
            return

except ConnectionError:
    logger.critical("Lost connection to broker")
    alert_admin("CRITICAL: Connection lost")
    # Try to reconnect
    reconnect_with_backoff()

except Exception as e:
    logger.exception("Unexpected error in main loop")
    alert_admin("System error", str(e))
    # Don't crash - continue next iteration
```

---

##### 2. **Circuit Breakers** (Safety Limits)

**Protections Against:**
- Overtrading (too many positions)
- Margin calls (insufficient capital)
- Runaway losses (stop trading if losing too much)
- System errors (stop if errors too frequent)

**Implementation:**
```python
class CircuitBreaker:
    def __init__(self):
        self.max_positions = 1
        self.max_daily_loss = 300  # $300/day
        self.max_consecutive_losses = 5
        self.max_errors_per_hour = 10

        self.daily_loss = 0
        self.consecutive_losses = 0
        self.errors_this_hour = []

    def can_trade(self):
        # Check all safety conditions
        if self.daily_loss >= self.max_daily_loss:
            return False, "Daily loss limit hit"

        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, "Too many consecutive losses"

        if len(self.errors_this_hour) >= self.max_errors_per_hour:
            return False, "Too many errors this hour"

        return True, "OK"

    def record_trade(self, pnl):
        self.daily_loss += abs(pnl) if pnl < 0 else 0

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def record_error(self):
        now = datetime.now()
        self.errors_this_hour.append(now)

        # Clean old errors
        one_hour_ago = now - timedelta(hours=1)
        self.errors_this_hour = [t for t in self.errors_this_hour if t > one_hour_ago]
```

---

##### 3. **Position Reconciliation** (Verify Reality)

**Problem:** Your code thinks you have 1 position, but broker shows 0 (order failed silently)

**Solution:** Every 5 minutes, verify:

```python
def reconcile_positions():
    """Verify our records match broker reality."""
    # Get positions from broker
    broker_positions = ib.positions()

    # Get positions from our system
    our_positions = db.get_open_positions()

    # Compare
    if len(broker_positions) != len(our_positions):
        logger.critical("Position mismatch!")
        alert_admin(f"CRITICAL: We think {len(our_positions)}, broker shows {len(broker_positions)}")

        # Force sync
        sync_positions_from_broker()
```

---

##### 4. **Order Validation** (Before Sending)

**Checks before every order:**

```python
def validate_order(symbol, size, order_type):
    """Verify order is safe before sending."""

    # Check 1: Do we have margin?
    margin_required = size * margin_per_contract
    available_margin = account.available_margin

    if margin_required > available_margin * 0.9:  # Use max 90% of margin
        return False, "Insufficient margin"

    # Check 2: Is position size reasonable?
    if size > max_position_size:
        return False, "Position too large"

    # Check 3: Are we already in a position?
    current_positions = get_open_positions(symbol)
    if len(current_positions) >= max_positions:
        return False, "Already have max positions"

    # Check 4: Is market open?
    if not market_is_open():
        return False, "Market closed"

    # Check 5: Circuit breakers
    can_trade, reason = circuit_breaker.can_trade()
    if not can_trade:
        return False, reason

    return True, "OK"
```

---

##### 5. **Automatic Reconnection**

**Problem:** Broker connection drops (happens daily)

**Solution:** Exponential backoff retry

```python
def reconnect_with_backoff(max_attempts=5):
    """Try to reconnect with increasing delays."""
    for attempt in range(max_attempts):
        wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s

        logger.info(f"Reconnect attempt {attempt+1}/{max_attempts} (waiting {wait_time}s)")
        time.sleep(wait_time)

        try:
            ib.connect()
            logger.info("Reconnected successfully")
            return True
        except Exception as e:
            logger.warning(f"Reconnect failed: {e}")

    logger.critical("Could not reconnect after max attempts")
    alert_admin("CRITICAL: Cannot reconnect to broker")
    return False
```

---

##### 6. **Heartbeat Monitoring**

**Problem:** System is running but stuck (infinite loop, deadlock)

**Solution:** Heartbeat file

```python
def update_heartbeat():
    """Write timestamp to file every minute."""
    with open('/tmp/trading_bot_heartbeat.txt', 'w') as f:
        f.write(str(time.time()))

# Separate monitoring script checks heartbeat
def check_heartbeat():
    try:
        with open('/tmp/trading_bot_heartbeat.txt', 'r') as f:
            last_heartbeat = float(f.read())

        if time.time() - last_heartbeat > 300:  # 5 minutes
            alert_admin("CRITICAL: Bot not responding (no heartbeat)")
            # Optionally restart bot
    except:
        alert_admin("CRITICAL: Heartbeat file missing")
```

---

#### Complete Error Handling Architecture:

```
┌─────────────────────────────────────────────────┐
│ Main Trading Loop                               │
│ ┌─────────────────────────────────────────────┐ │
│ │ Try:                                        │ │
│ │   1. Fetch data                             │ │
│ │   2. Calculate indicators                   │ │
│ │   3. Generate signals                       │ │
│ │   4. Validate order                         │ │
│ │   5. Send order                             │ │
│ │   6. Confirm fill                           │ │
│ │   7. Update database                        │ │
│ │   8. Update heartbeat                       │ │
│ └─────────────────────────────────────────────┘ │
│                                                   │
│ Except ConnectionError:                          │
│   → Log error                                    │
│   → Try reconnect                                │
│   → If fail, alert admin                         │
│                                                   │
│ Except BrokerError:                               │
│   → Log error                                    │
│   → Don't crash                                  │
│   → Continue next iteration                      │
│                                                   │
│ Except Exception:                                 │
│   → Log full traceback                           │
│   → Alert admin                                  │
│   → Continue (don't crash)                       │
│                                                   │
│ Finally:                                          │
│   → Reconcile positions (every 5 min)           │
│   → Check circuit breakers                       │
│   → Update metrics                               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Monitoring Layer (Separate Process)             │
├─────────────────────────────────────────────────┤
│ Every 1 minute:                                 │
│  - Check heartbeat                              │
│  - Verify process running                       │
│  - Check disk space                             │
│  - Check memory usage                           │
│                                                   │
│ Every 5 minutes:                                 │
│  - Reconcile positions                          │
│  - Verify account balance                       │
│  - Check for orphaned orders                    │
│                                                   │
│ Every 1 hour:                                    │
│  - Generate metrics report                      │
│  - Check for pattern anomalies                  │
│  - Backup database                              │
│                                                   │
│ Every day (8 AM):                                │
│  - Send daily summary email                     │
│  - Reset daily counters                         │
│  - Archive logs                                 │
└─────────────────────────────────────────────────┘
```

---

### D. **Safety Against Specific Risks**

#### 1. **Overtrading Protection**

```python
# Hard limits
MAX_TRADES_PER_DAY = 50
MAX_POSITIONS_AT_ONCE = 1
MIN_SECONDS_BETWEEN_TRADES = 60

class TradeLimiter:
    def __init__(self):
        self.trades_today = 0
        self.last_trade_time = None

    def can_trade(self):
        now = datetime.now()

        # Check daily limit
        if self.trades_today >= MAX_TRADES_PER_DAY:
            return False, "Max trades per day reached"

        # Check time since last trade
        if self.last_trade_time:
            seconds_since = (now - self.last_trade_time).total_seconds()
            if seconds_since < MIN_SECONDS_BETWEEN_TRADES:
                return False, f"Too soon since last trade ({seconds_since}s)"

        return True, "OK"
```

---

#### 2. **Margin Call Protection**

```python
def check_margin_safety():
    """Verify we have enough margin."""
    account = ib.accountSummary()

    available_margin = account['AvailableFunds']
    margin_requirement = account['MaintMarginReq']

    # Calculate utilization
    margin_usage_pct = (margin_requirement / available_margin) * 100

    # Alert levels
    if margin_usage_pct > 90:
        logger.critical(f"Margin usage: {margin_usage_pct:.1f}%")
        alert_admin("CRITICAL: Margin usage > 90%")
        # Close all positions immediately
        emergency_close_all_positions()

    elif margin_usage_pct > 75:
        logger.warning(f"Margin usage: {margin_usage_pct:.1f}%")
        alert_admin(f"WARNING: Margin usage {margin_usage_pct:.1f}%")
        # Stop opening new positions
        circuit_breaker.halt_trading()

    return margin_usage_pct
```

---

#### 3. **Accidental Order Duplication**

```python
class OrderTracker:
    def __init__(self):
        self.pending_orders = {}
        self.lock = threading.Lock()

    def submit_order(self, symbol, direction, size):
        """Prevent duplicate orders."""
        with self.lock:
            # Create order fingerprint
            order_key = f"{symbol}_{direction}_{size}"

            # Check if already pending
            if order_key in self.pending_orders:
                logger.warning(f"Duplicate order detected: {order_key}")
                return False, "Order already pending"

            # Submit order
            order_id = ib.submit_order(symbol, direction, size)

            # Track it
            self.pending_orders[order_key] = {
                'order_id': order_id,
                'timestamp': datetime.now()
            }

            return True, order_id

    def mark_filled(self, order_id):
        """Remove from pending when filled."""
        with self.lock:
            for key, val in list(self.pending_orders.items()):
                if val['order_id'] == order_id:
                    del self.pending_orders[key]
                    break
```

---

## 3. PUTTING IT ALL TOGETHER

### Production System Architecture:

```
┌──────────────────────────────────────────────────────────┐
│ SERVER (Oracle Cloud / AWS / DigitalOcean)              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ Trading Bot (Main Process)                  │        │
│  │  - Connects to IB                           │        │
│  │  - Runs strategy logic                      │        │
│  │  - Places orders                            │        │
│  │  - Logs to SQLite                           │        │
│  │  - Writes metrics to InfluxDB               │        │
│  │  - Updates heartbeat file                   │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ Monitor Process (Separate)                  │        │
│  │  - Checks heartbeat                         │        │
│  │  - Reconciles positions                     │        │
│  │  - Sends daily email                        │        │
│  │  - Restarts bot if crashed                  │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ Databases                                    │        │
│  │  - SQLite (trade log)                       │        │
│  │  - InfluxDB (metrics)                       │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ Grafana (Dashboard)                         │        │
│  │  - Port 3000 → Access from browser         │        │
│  │  - Shows equity, P&L, positions             │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
└──────────────────────────────────────────────────────────┘
                          │
                          │ Internet
                          │
         ┌────────────────┴────────────────┐
         │                                  │
    ┌────▼─────┐                      ┌────▼─────┐
    │ Your     │                      │ IB TWS / │
    │ Phone/   │                      │ Gateway  │
    │ Laptop   │                      │          │
    └──────────┘                      └──────────┘
    - Check Grafana                   - Live trading
    - Read email                      - Real-time data
    - Review trades                   - Order execution
```

---

### Monthly Cost Breakdown:

| Component | Option | Cost |
|-----------|--------|------|
| **Server** | Oracle Cloud Free Tier | $0 |
| **Database** | SQLite + InfluxDB (self-hosted) | $0 |
| **Monitoring** | Grafana (self-hosted) | $0 |
| **Alerting** | Email (Gmail SMTP) | $0 |
| **SMS Alerts** | Twilio (emergency only) | $5-10 |
| **IB Data Feed** | Real-time MES | $0-10 |
| **TOTAL** | | **$5-20/month** |

**Or:**

| Component | Paid Option | Cost |
|-----------|-------------|------|
| **Server** | DigitalOcean Droplet | $12 |
| **Database** | Managed PostgreSQL | $15 |
| **Monitoring** | Datadog | $15 |
| **Alerting** | Included | $0 |
| **TOTAL** | | **$42/month** |

---

## 4. IMPLEMENTATION TIMELINE

### Week 1 (While IB Approves):
- [x] Strategy comparison done
- [ ] Set up Oracle Cloud account
- [ ] Deploy basic server
- [ ] Install Python + dependencies

### Week 2:
- [ ] Implement circuit breakers in code
- [ ] Add SQLite trade logging
- [ ] Create monitoring script
- [ ] Set up email alerts

### Week 3:
- [ ] Install InfluxDB + Grafana
- [ ] Create dashboard
- [ ] Connect to IB paper account
- [ ] Test order execution

### Week 4:
- [ ] Paper trading begins
- [ ] Daily monitoring
- [ ] Fix any issues

---

## 5. NEXT STEPS (Your Decision)

**I can start building the infrastructure NOW while IB approves. Here's what I'll do:**

1. **Create production-ready trading bot code** with:
   - Robust error handling
   - Circuit breakers
   - Position reconciliation
   - SQLite logging
   - Heartbeat monitoring

2. **Create monitoring system**:
   - Daily email script
   - Health check script
   - Dashboard setup guide

3. **Create deployment guide**:
   - Step-by-step Oracle Cloud setup
   - Server configuration
   - Running the bot
   - Checking logs

**Should I proceed?**

---

**END OF INFRASTRUCTURE PLAN**
