"""
Component Test Runner

Runs multiple strategy variants and produces a comparison table.
Follows claude.md methodology: test ONE change at a time,
compare each variant against the baseline independently.

Usage:
    python tools/component_test.py <data_file>

Example:
    python tools/component_test.py MES_5mins_2025-02-14_to_2026-02-13_REAL.csv
"""

import subprocess
import re
import sys
import os


# Define test variants
# Each test changes ONE variable from the baseline (v1_atr_filter)
TESTS = {
    'baseline': {
        'config': 'config/strategies/v1_atr_filter.yaml',
        'description': 'V1 + ATR filter (current best)',
        'change': 'None (baseline)',
    },
    'low_volume': {
        'config': 'config/strategies/test_low_volume_filter.yaml',
        'description': 'V1+ATR only on low volume (<0.9x avg)',
        'change': 'max_volume_ratio: 0.9 (low-volume entries only)',
    },
    'bb_width_07': {
        'config': 'config/strategies/test_bb_width_07.yaml',
        'description': 'V1+ATR with BB width >= 0.7% (recalibrated)',
        'change': 'min_bb_width_pct: 0.7 (was 1.2 - miscalibrated)',
    },
    'no_friday': {
        'config': 'config/strategies/test_no_friday.yaml',
        'description': 'V1+ATR without Friday trades',
        'change': 'Exclude Friday (pre-weekend position squaring)',
    },
}


def parse_backtest_output(output):
    """Parse key metrics from backtest stdout."""
    patterns = {
        'total_return_pct': r'Total Return:\s+([-\d.]+)%',
        'sharpe_ratio': r'Sharpe Ratio:\s+([-\d.]+)',
        'max_drawdown_pct': r'Max Drawdown:\s+([-\d.]+)%',
        'total_trades': r'Total Trades:\s+(\d+)',
        'win_rate': r'Win Rate:\s+([-\d.]+)%',
        'profit_factor': r'Profit Factor:\s+([-\d.]+)',
        'avg_win': r'Avg Win: \$\s*([-\d.,]+)',
        'avg_loss': r'Avg Loss: \$\s*([-\d.,]+)',
        'total_pnl': r'Total P&L: \$\s*([-\d.,]+)',
    }

    metrics = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            val = match.group(1).replace(',', '')
            metrics[key] = float(val) if '.' in val else int(val)
        else:
            metrics[key] = 0

    return metrics


def run_backtest(config_file, data_file):
    """Run a single backtest and return parsed metrics."""
    cmd = [
        'python', 'src/backtest/run_backtest.py',
        '--config', config_file,
        '--data-file', data_file
    ]

    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    output = result.stdout + result.stderr
    return parse_backtest_output(output)


def run_walk_forward(config_file, data_file):
    """Run walk-forward test and return parsed metrics per period.

    Uses a temp JSON file for reliable cross-process communication,
    with stdout pipe-delimited parsing as fallback.
    """
    import json
    import tempfile

    os.makedirs('logs', exist_ok=True)

    # Create temp file for walk-forward to write results to
    wf_output = tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                             delete=False, dir='logs')
    wf_output_path = wf_output.name
    wf_output.close()

    cmd = [
        'python', 'tools/walk_forward_test.py',
        config_file,
        data_file
    ]

    # Pass output file path via environment variable
    env = os.environ.copy()
    env['WF_OUTPUT_FILE'] = wf_output_path

    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', env=env)

    stdout = result.stdout or ''
    stderr = result.stderr or ''
    output = stdout + stderr

    # Method 1: Read from JSON file (most reliable)
    periods = {}
    json_err = None
    try:
        with open(wf_output_path, 'r') as f:
            content = f.read()
        if content.strip():
            wf_json = json.loads(content)
            for period, data in wf_json.items():
                periods[period] = {
                    'return': float(data['return']),
                    'sharpe': float(data['sharpe']),
                    'trades': int(data['trades']),
                    'win_rate': float(data['win_rate']),
                    'pf': float(data['pf']),
                }
        else:
            json_err = "JSON file was empty"
    except FileNotFoundError:
        json_err = "JSON file not found"
    except json.JSONDecodeError as e:
        json_err = f"JSON decode error: {e}"
    except KeyError as e:
        json_err = f"Missing key: {e}"
    except Exception as e:
        json_err = f"Error: {e}"
    finally:
        try:
            os.unlink(wf_output_path)
        except OSError:
            pass

    if periods:
        return periods

    # Method 2: Parse pipe-delimited WF| lines from stdout
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('WF|'):
            parts = line.split('|')
            if len(parts) == 7:
                period = parts[1]
                periods[period] = {
                    'return': float(parts[2]),
                    'sharpe': float(parts[3]),
                    'trades': int(parts[4]),
                    'win_rate': float(parts[5]),
                    'pf': float(parts[6]),
                }

    if periods:
        return periods

    # Method 3: Regex on summary table
    for period in ['train', 'test', 'validate']:
        pattern = rf'{period.capitalize()}\s+([-\d.]+)%\s+([-\d.]+)\s+(\d+)\s+([-\d.]+)%\s+([-\d.]+)'
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            periods[period] = {
                'return': float(match.group(1)),
                'sharpe': float(match.group(2)),
                'trades': int(match.group(3)),
                'win_rate': float(match.group(4)),
                'pf': float(match.group(5)),
            }

    # If all methods failed, print diagnostic info
    if not periods:
        print(f"\n    [DEBUG] WF parse failed for {os.path.basename(config_file)}")
        print(f"    [DEBUG] Return code: {result.returncode}")
        print(f"    [DEBUG] JSON method: {json_err}")
        # Show last 15 lines of output for clues
        lines = output.strip().splitlines()
        tail = lines[-15:] if len(lines) > 15 else lines
        if tail:
            print(f"    [DEBUG] Last {len(tail)} lines of output:")
            for l in tail:
                print(f"      {l}")
        else:
            print(f"    [DEBUG] No output captured from subprocess")

    return periods


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/component_test.py <data_file>")
        print("\nExample:")
        print("  python tools/component_test.py MES_5mins_2025-02-14_to_2026-02-13_REAL.csv")
        sys.exit(1)

    data_file = sys.argv[1]

    print("=" * 80)
    print("COMPONENT TEST SUITE")
    print("=" * 80)
    print(f"\nData: {data_file}")
    print(f"Tests: {len(TESTS)}")
    print(f"\nMethodology: Each test changes ONE variable from baseline.")
    print(f"Baseline: V1 + ATR filter (config/strategies/v1_atr_filter.yaml)")

    # Phase 1: Full backtest on all variants
    print(f"\n{'=' * 80}")
    print("PHASE 1: FULL BACKTEST (all data)")
    print("=" * 80)

    full_results = {}
    for name, test in TESTS.items():
        print(f"\n  Running {name}... ", end='', flush=True)
        metrics = run_backtest(test['config'], data_file)
        full_results[name] = metrics

        if metrics['total_trades'] > 0:
            print(f"{metrics['total_trades']} trades, "
                  f"{metrics['total_return_pct']:.2f}%, "
                  f"PF {metrics['profit_factor']:.2f}")
        else:
            print("0 trades!")

    # Print full results table
    print(f"\n{'=' * 80}")
    print("FULL BACKTEST COMPARISON")
    print("=" * 80)

    header = f"{'Variant':<18} {'Return':>8} {'Trades':>7} {'WinRate':>8} {'PF':>6} {'Sharpe':>7} {'MaxDD':>7} {'AvgWin':>8} {'AvgLoss':>8}"
    print(f"\n{header}")
    print("-" * 80)

    baseline_return = full_results.get('baseline', {}).get('total_return_pct', 0)

    for name, metrics in full_results.items():
        ret = metrics['total_return_pct']
        diff = ret - baseline_return if name != 'baseline' else 0

        marker = ''
        if name != 'baseline':
            marker = ' +' if diff > 0 else ' '

        print(f"{name:<18} {ret:>7.2f}% {metrics['total_trades']:>7} "
              f"{metrics['win_rate']:>7.1f}% {metrics['profit_factor']:>6.2f} "
              f"{metrics['sharpe_ratio']:>7.2f} {metrics['max_drawdown_pct']:>6.2f}% "
              f"${metrics['avg_win']:>7.2f} ${metrics['avg_loss']:>7.2f}"
              f"{marker}{diff:.2f}%" if name != 'baseline' else
              f"{name:<18} {ret:>7.2f}% {metrics['total_trades']:>7} "
              f"{metrics['win_rate']:>7.1f}% {metrics['profit_factor']:>6.2f} "
              f"{metrics['sharpe_ratio']:>7.2f} {metrics['max_drawdown_pct']:>6.2f}% "
              f"${metrics['avg_win']:>7.2f} ${metrics['avg_loss']:>7.2f}  <-- BASELINE")

    # Phase 2: Walk-forward test on all variants
    print(f"\n{'=' * 80}")
    print("PHASE 2: WALK-FORWARD TEST (train/test/validate)")
    print("=" * 80)

    wf_results = {}
    for name, test in TESTS.items():
        print(f"\n  Running walk-forward: {name}... ", flush=True)
        periods = run_walk_forward(test['config'], data_file)
        wf_results[name] = periods

        for period, data in periods.items():
            print(f"    {period}: {data['return']:.2f}%, "
                  f"{data['trades']} trades, PF {data['pf']:.2f}")

    # Print walk-forward comparison
    print(f"\n{'=' * 80}")
    print("WALK-FORWARD COMPARISON BY PERIOD")
    print("=" * 80)

    for period in ['train', 'test', 'validate']:
        print(f"\n  {period.upper()} PERIOD:")
        print(f"  {'Variant':<18} {'Return':>8} {'Trades':>7} {'WinRate':>8} {'PF':>6}")
        print(f"  {'-' * 50}")

        has_data = False
        for name in TESTS:
            if period in wf_results.get(name, {}):
                data = wf_results[name][period]
                has_data = True
                pf_str = f"{data['pf']:>6.2f}" if data['pf'] > 0 else "   N/A"
                print(f"  {name:<18} {data['return']:>7.2f}% {data['trades']:>7} "
                      f"{data['win_rate']:>7.1f}% {pf_str}")

        if not has_data:
            print(f"  (no data parsed for this period)")

    # Phase 3: Verdict
    print(f"\n{'=' * 80}")
    print("COMPONENT ANALYSIS")
    print("=" * 80)

    baseline_full = full_results.get('baseline', {})

    for name, test in TESTS.items():
        if name == 'baseline':
            continue

        metrics = full_results.get(name, {})
        wf = wf_results.get(name, {})

        print(f"\n  {name}: {test['change']}")

        # Full backtest comparison
        ret_diff = metrics['total_return_pct'] - baseline_full['total_return_pct']
        pf_diff = metrics['profit_factor'] - baseline_full['profit_factor']

        if ret_diff > 1:
            print(f"    Full backtest: +{ret_diff:.2f}% vs baseline (BETTER)")
        elif ret_diff < -1:
            print(f"    Full backtest: {ret_diff:.2f}% vs baseline (WORSE)")
        else:
            print(f"    Full backtest: {ret_diff:+.2f}% vs baseline (SIMILAR)")

        # Walk-forward comparison - check both test AND validate
        base_test = wf_results.get('baseline', {}).get('test', {})
        base_val = wf_results.get('baseline', {}).get('validate', {})
        var_test = wf.get('test', {})
        var_val = wf.get('validate', {})

        if base_test and var_test:
            test_diff = var_test['return'] - base_test['return']
            if test_diff > 0.5:
                print(f"    Out-of-sample (test):     +{test_diff:.2f}% (BETTER)")
            elif test_diff < -0.5:
                print(f"    Out-of-sample (test):     {test_diff:.2f}% (WORSE)")
            else:
                print(f"    Out-of-sample (test):     {test_diff:+.2f}% (SIMILAR)")

        if base_val and var_val:
            val_diff = var_val['return'] - base_val['return']
            if val_diff > 0.5:
                print(f"    Out-of-sample (validate): +{val_diff:.2f}% (BETTER)")
            elif val_diff < -0.5:
                print(f"    Out-of-sample (validate): {val_diff:.2f}% (WORSE)")
            else:
                print(f"    Out-of-sample (validate): {val_diff:+.2f}% (SIMILAR)")

        # Verdict: requires improvement in BOTH out-of-sample periods
        # (not just test - that prevents false positives from lucky test splits)
        val_ok = var_val.get('return', -999) > base_val.get('return', 0) if (var_val and base_val) else None
        test_ok = var_test.get('return', -999) > base_test.get('return', 0) if (var_test and base_test) else None
        dd_ok = metrics['max_drawdown_pct'] > baseline_full['max_drawdown_pct'] - 3  # allow 3% more drawdown

        if ret_diff > 1 and test_ok and val_ok and dd_ok:
            print(f"    --> ADOPT: Improves full backtest AND both out-of-sample periods")
        elif ret_diff > 1 and (not test_ok or not val_ok):
            if not val_ok:
                print(f"    --> REJECT: In-sample gain doesn't hold in validate period (overfitting)")
            else:
                print(f"    --> REJECT: In-sample gain doesn't hold out-of-sample (overfitting)")
        elif ret_diff > 1 and not dd_ok:
            print(f"    --> REJECT: Return improvement offset by excessive drawdown increase")
        elif ret_diff < -1:
            print(f"    --> REJECT: Worse full-backtest performance")
        else:
            print(f"    --> NEUTRAL: No significant difference")

    print(f"\n{'=' * 80}")
    print("NEXT STEPS")
    print("=" * 80)
    print(f"\n  1. Adopt any components marked ADOPT")
    print(f"  2. Reject any marked REJECT or NEUTRAL")
    print(f"  3. Run walk-forward on combined improvements")
    print(f"  4. Only deploy if ALL periods are profitable")
    print(f"\n{'=' * 80}\n")


if __name__ == '__main__':
    main()
