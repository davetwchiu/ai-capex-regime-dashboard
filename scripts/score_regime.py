import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import csv

# Load configs and retrieval stats
with open('config/tickers.json', 'r') as f: tickers = json.load(f)
with open('config/weights.json', 'r') as f: weights = json.load(f)

try:
    with open('data/warnings.json', 'r') as f: warnings = json.load(f)
except FileNotFoundError:
    warnings = []

try:
    with open('data/retrieval_stats.json', 'r') as f: ret_stats = json.load(f)
except FileNotFoundError:
    ret_stats = {"expected_tickers": 0, "retrieved_tickers": 0, "failed_tickers": []}

df = pd.read_csv('data/raw_prices.csv')
df['date'] = pd.to_datetime(df['date'])

pivot_df = df.pivot(index='date', columns='ticker', values='close').sort_index()
latest_date_obj = pivot_df.index[-1]
latest_date = latest_date_obj.strftime('%Y-%m-%d')

# Utility Functions
def get_return(ticker, days):
    if ticker not in pivot_df.columns: return 0
    series = pivot_df[ticker].dropna()
    if len(series) < days + 1: return 0
    return (series.iloc[-1] / series.iloc[-(days+1)]) - 1

def get_basket_return(basket, days):
    returns = [get_return(t, days) for t in basket if t in pivot_df.columns]
    return np.mean(returns) if returns else 0

def normalize(val, scale=None):
    clip_val = scale if scale else weights['normalization']['max_return_clip']
    score = 50 + (val / clip_val) * 50
    return max(0, min(100, score))

# 1. Demand Score
demand_20 = get_basket_return(tickers['demand'], 20) - get_return('QQQ', 20)
demand_60 = get_basket_return(tickers['demand'], 60) - get_return('QQQ', 60)
demand_120 = get_basket_return(tickers['demand'], 120) - get_return('QQQ', 120)
demand_score = normalize((demand_20 * 0.4) + (demand_60 * 0.4) + (demand_120 * 0.2))

# 2. Bottleneck Score
bot_20 = get_basket_return(tickers['bottleneck'], 20) - get_return('SMH', 20)
bot_60 = get_basket_return(tickers['bottleneck'], 60) - get_return('SMH', 60)
bot_120 = get_basket_return(tickers['bottleneck'], 120) - get_return('SMH', 120)
bottleneck_score = normalize((bot_20 * 0.4) + (bot_60 * 0.4) + (bot_120 * 0.2))

# 3. Substitution (ASIC / Networking Rotation) Score (using wider clip)
sub_20 = get_basket_return(['AVGO', 'MRVL', 'ANET', 'CRDO'], 20) - get_return('NVDA', 20)
sub_60 = get_basket_return(['AVGO', 'MRVL', 'ANET', 'CRDO'], 60) - get_return('NVDA', 60)
rotation_clip = weights['normalization'].get('rotation_clip', 0.25)
substitution_score = normalize((sub_20 * 0.5) + (sub_60 * 0.5), scale=rotation_clip)

# 4. Composite Stress Score
stress_underperf = get_basket_return(tickers['stress'], 20) - get_return('QQQ', 20)
norm_underperf = max(0, min(100, 50 - (stress_underperf / 0.15) * 50))

drawdowns = []
for t in tickers['stress']:
    if t in pivot_df.columns:
        series = pivot_df[t].dropna()
        if len(series) >= 60:
            dd = (series.iloc[-1] / series.tail(60).max()) - 1
            drawdowns.append(dd)
avg_dd = np.mean(drawdowns) if drawdowns else 0
norm_dd = max(0, min(100, (avg_dd / -0.30) * 100))

credit_diff = get_return('HYG', 20) - get_return('LQD', 20)
norm_credit = max(0, min(100, 50 - (credit_diff / 0.05) * 50))

stress_score = (norm_underperf * 0.50) + (norm_dd * 0.35) + (norm_credit * 0.15)

# 5. Composite Breadth Score
universe = set(tickers['demand'] + tickers['bottleneck'] + tickers['networking_optical'] + tickers['power_cooling'] + tickers['stress'])
valid_tickers = 0
conditions_true = 0
b_metrics = {'20d':0, '50d':0, 'qqq':0, 'smh':0}

qqq_20d = get_return('QQQ', 20)
smh_20d = get_return('SMH', 20)

for t in universe:
    if t in pivot_df.columns:
        series = pivot_df[t].dropna()
        if len(series) >= 50:
            valid_tickers += 1
            p = series.iloc[-1]
            ret_20 = get_return(t, 20)
            
            if p > series.rolling(20).mean().iloc[-1]: 
                conditions_true += 1
                b_metrics['20d'] += 1
            if p > series.rolling(50).mean().iloc[-1]: 
                conditions_true += 1
                b_metrics['50d'] += 1
            if ret_20 > qqq_20d: 
                conditions_true += 1
                b_metrics['qqq'] += 1
            if ret_20 > smh_20d: 
                conditions_true += 1
                b_metrics['smh'] += 1

conditions_total = valid_tickers * 4
breadth_score = (conditions_true / conditions_total) * 100 if conditions_total > 0 else 50

# --- Vector / Distance based Regime Mapping ---
scores_arr = np.array([demand_score, bottleneck_score, substitution_score, stress_score, breadth_score])
distances = []

for code, vec in weights['target_vectors'].items():
    vec_arr = np.array([vec['demand'], vec['bottleneck'], vec['substitution'], vec['stress'], vec['breadth']])
    dist = np.linalg.norm(scores_arr - vec_arr)
    distances.append((code, vec['name'], dist))

distances.sort(key=lambda x: x[2])
closest = distances[0]
second_closest = distances[1]

ratio = closest[2] / second_closest[2] if second_closest[2] > 0 else 0
if ratio <= 0.75: confidence = "High"
elif ratio <= 0.90: confidence = "Medium"
else: confidence = "Low"

# Hard Threshold checking
h, l = weights['thresholds']['high'], weights['thresholds']['low']
regime = "Mixed / Transition"
regime_name = "Transitioning Regime"

if demand_score >= h and bottleneck_score >= h and stress_score < h:
    regime, regime_name = "A", weights['target_vectors']['A']['name']
elif demand_score >= h and bottleneck_score < h and substitution_score >= h:
    regime, regime_name = "B", weights['target_vectors']['B']['name']
elif bottleneck_score >= h and demand_score < h and stress_score >= h:
    regime, regime_name = "C", weights['target_vectors']['C']['name']
elif demand_score < l and bottleneck_score < l and stress_score >= h:
    regime, regime_name = "D", weights['target_vectors']['D']['name']

# --- Divergence Warnings ---
divergences = []
nvda_vs_qqq = get_return('NVDA', 20) - qqq_20d
tsm_vs_smh = get_return('TSM', 20) - smh_20d

if nvda_vs_qqq > 0.05 and demand_score < 50:
    divergences.append({"type": "NVDA_Demand_Divergence", "message": "NVIDIA is outperforming QQQ, but demand/platform confirmation is weak."})
if tsm_vs_smh < -0.05:
    divergences.append({"type": "TSM_Underperformance", "message": "TSM is underperforming SMH over 20D, suggesting foundry leadership is not confirming broader semiconductor strength."})
if substitution_score > 85:
    divergences.append({"type": "High_Rotation", "message": "ASIC/networking rotation is very strong versus NVDA. Market may be shifting to custom silicon/scale-out."})
if bottleneck_score > 60 and stress_score > 60:
    divergences.append({"type": "Late_Cycle_Squeeze", "message": "Hardware bottleneck stocks remain strong while stress is rising. This can resemble a late-cycle squeeze."})
if bottleneck_score > 60 and breadth_score < 45:
    divergences.append({"type": "Narrow_Leadership", "message": "Bottleneck strength is narrow. Fewer AI-chain stocks are confirming the move."})

# --- Data Health Logic ---
now = datetime.now(timezone.utc)
age_days = (now.date() - latest_date_obj.date()).days
is_stale = age_days > 3

core_tickers = ["QQQ", "SMH", "SPY", "NVDA", "TSM", "MSFT", "AMZN", "GOOGL", "META", "AVGO", "HYG", "LQD"]
failed = ret_stats.get("failed_tickers", [])
core_missing = [t for t in core_tickers if t in failed]
core_ok = len(core_missing) == 0

expected = ret_stats.get("expected_tickers", 1)
retrieved = ret_stats.get("retrieved_tickers", 0)
ret_pct = (retrieved / expected) * 100 if expected > 0 else 0

if is_stale:
    status = "Stale"
elif ret_pct < 80 or not core_ok:
    status = "Failed"
elif ret_pct >= 95 and core_ok:
    status = "OK"
else:
    status = "Partial"

msg = f"Data retrieval {status}. {retrieved} of {expected} tickers retrieved."
if core_missing: msg += f" Core missing: {', '.join(core_missing)}."
elif not core_ok: msg += " Core tickers missing."
else: msg += " Core tickers available."

data_health = {
    "status": status,
    "source": "yfinance",
    "retrieved_tickers": retrieved,
    "expected_tickers": expected,
    "retrieval_success_pct": round(ret_pct, 1),
    "failed_tickers": failed,
    "core_tickers_ok": core_ok,
    "core_missing_tickers": core_missing,
    "latest_trading_date": latest_date,
    "last_updated_utc": now.isoformat(),
    "is_stale": is_stale,
    "message": msg
}

# --- Output Assembly ---
output = {
    "date": latest_date,
    "last_updated_utc": now.isoformat(),
    "data_health": data_health,
    "data_freshness": {
        "latest_trading_date": latest_date,
        "calendar_age_days": age_days,
        "is_stale": is_stale
    },
    "regime": regime,
    "regime_name": regime_name,
    "closest_regime": {
        "code": closest[0],
        "name": closest[1]
    },
    "confidence": confidence,
    "divergence_warnings": divergences,
    "scores": {
        "demand": round(demand_score, 1),
        "bottleneck": round(bottleneck_score, 1),
        "substitution": round(substitution_score, 1),
        "stress": round(stress_score, 1),
        "breadth": round(breadth_score, 1)
    },
    "breadth_details": {
        "valid_tickers": valid_tickers,
        "conditions_true": conditions_true,
        "conditions_total": conditions_total,
        "above_20dma_pct": round((b_metrics['20d'] / valid_tickers) * 100, 1) if valid_tickers else 0,
        "above_50dma_pct": round((b_metrics['50d'] / valid_tickers) * 100, 1) if valid_tickers else 0,
        "outperforming_qqq_20d_pct": round((b_metrics['qqq'] / valid_tickers) * 100, 1) if valid_tickers else 0,
        "outperforming_smh_20d_pct": round((b_metrics['smh'] / valid_tickers) * 100, 1) if valid_tickers else 0
    },
    "stress_details": {
        "underperformance_component": round(norm_underperf, 1),
        "drawdown_component": round(norm_dd, 1),
        "credit_component": round(norm_credit, 1),
        "average_stress_basket_60d_drawdown": round(avg_dd * 100, 2)
    },
    "key_ratios": {
        "NVDA_QQQ_20D": round(nvda_vs_qqq * 100, 2),
        "TSM_SMH_20D": round(tsm_vs_smh * 100, 2),
        "AVGO_NVDA_20D": round((get_return('AVGO', 20) - get_return('NVDA', 20)) * 100, 2),
        "HYG_LQD_20D": round(credit_diff * 100, 2)
    },
    "warnings": warnings
}

with open('data/latest.json', 'w') as f:
    json.dump(output, f, indent=2)

# --- History Updates ---
history_file = 'data/history.json'
hist_data = []
if os.path.exists(history_file):
    with open(history_file, 'r') as f:
        hist_data = json.load(f)

hist_data = [d for d in hist_data if d['date'] != latest_date]
hist_data.append({
    "date": latest_date,
    "regime": regime,
    "regime_name": regime_name,
    "closest_regime": output['closest_regime'],
    "confidence": confidence,
    "scores": output['scores']
})

with open(history_file, 'w') as f:
    json.dump(hist_data[-250:], f, indent=2)

# CSV History
csv_file = 'data/score_history.csv'
csv_exists = os.path.exists(csv_file)
csv_rows = []
if csv_exists:
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        csv_rows = [row for row in reader if row['date'] != latest_date]

csv_rows.append({
    'date': latest_date,
    'demand_score': round(demand_score, 1),
    'bottleneck_score': round(bottleneck_score, 1),
    'substitution_score': round(substitution_score, 1),
    'stress_score': round(stress_score, 1),
    'breadth_score': round(breadth_score, 1),
    'regime': regime
})

with open(csv_file, 'w', newline='') as f:
    writer = csv.DictReader(open(csv_file)) if csv_exists else None
    fieldnames = ['date', 'demand_score', 'bottleneck_score', 'substitution_score', 'stress_score', 'breadth_score', 'regime']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"Update complete. Date: {latest_date} | Health: {status} | Closest: {closest[0]}")
