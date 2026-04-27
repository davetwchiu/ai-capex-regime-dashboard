import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Load configs
with open('config/tickers.json', 'r') as f: tickers = json.load(f)
with open('config/weights.json', 'r') as f: weights = json.load(f)
with open('data/warnings.json', 'r') as f: warnings = json.load(f)

df = pd.read_csv('data/raw_prices.csv')
df['date'] = pd.to_datetime(df['date'])

# Pivot table to get dates on index and tickers on columns
pivot_df = df.pivot(index='date', columns='ticker', values='close').sort_index()

# Utility to calculate N-day returns
def get_return(ticker, days):
    if ticker not in pivot_df.columns: return 0
    series = pivot_df[ticker].dropna()
    if len(series) < days + 1: return 0
    return (series.iloc[-1] / series.iloc[-(days+1)]) - 1

# Utility to calculate basket average return
def get_basket_return(basket, days):
    returns = [get_return(t, days) for t in basket if t in pivot_df.columns]
    return np.mean(returns) if returns else 0

# Normalization (-15% to +15% maps to 0-100)
def normalize(val):
    clip_val = weights['normalization']['max_return_clip']
    score = 50 + (val / clip_val) * 50
    return max(0, min(100, score))

# 1. Demand Score (Demand basket vs QQQ)
demand_20 = get_basket_return(tickers['demand'], 20) - get_return('QQQ', 20)
demand_60 = get_basket_return(tickers['demand'], 60) - get_return('QQQ', 60)
demand_120 = get_basket_return(tickers['demand'], 120) - get_return('QQQ', 120)

demand_raw = (demand_20 * 0.4) + (demand_60 * 0.4) + (demand_120 * 0.2)
demand_score = normalize(demand_raw)

# 2. Bottleneck Score (Bottleneck vs SMH)
bot_20 = get_basket_return(tickers['bottleneck'], 20) - get_return('SMH', 20)
bot_60 = get_basket_return(tickers['bottleneck'], 60) - get_return('SMH', 60)
bot_120 = get_basket_return(tickers['bottleneck'], 120) - get_return('SMH', 120)

bot_raw = (bot_20 * 0.4) + (bot_60 * 0.4) + (bot_120 * 0.2)
bottleneck_score = normalize(bot_raw)

# 3. Substitution Score (Network/ASIC vs NVDA)
sub_20 = get_basket_return(['AVGO', 'MRVL', 'ANET', 'CRDO'], 20) - get_return('NVDA', 20)
sub_60 = get_basket_return(['AVGO', 'MRVL', 'ANET', 'CRDO'], 60) - get_return('NVDA', 60)
sub_raw = (sub_20 * 0.5) + (sub_60 * 0.5)
substitution_score = normalize(sub_raw)

# 4. Stress Score (High Beta AI Underperformance + Credit Weakness)
stress_basket = get_basket_return(tickers['stress'], 20) - get_return('QQQ', 20)
credit_ratio = get_return('HYG', 20) - get_return('LQD', 20)
# Inverse logic: If stress basket underperforms (-), stress is high (+). If HYG underperforms (-), stress is high (+).
stress_raw = (-stress_basket * 0.7) + (-credit_ratio * 0.3)
stress_score = normalize(stress_raw)

# 5. Breadth Score (% of core universe above 20D MA)
core_univ = tickers['demand'] + tickers['bottleneck']
above_20d = 0
for t in set(core_univ):
    if t in pivot_df.columns:
        series = pivot_df[t].dropna()
        if len(series) >= 20 and series.iloc[-1] > series.rolling(20).mean().iloc[-1]:
            above_20d += 1
breadth_score = (above_20d / len(set(core_univ))) * 100 if core_univ else 50

# Regime Classification
regime = "Mixed / Transition"
regime_name = "Transitioning Regime"
summary = "Market signals are mixed. Waiting for clearer trend alignment across demand, bottleneck, and stress metrics."

h, l = weights['thresholds']['high'], weights['thresholds']['low']

if demand_score >= h and bottleneck_score >= h and stress_score < h:
    regime = "A"
    regime_name = "True Bottleneck Still Tight"
    summary = "Healthy CAPEX expansion. Market is pricing strong AI ROI and continuing hardware scarcity."
elif demand_score >= h and bottleneck_score < h and substitution_score >= h:
    regime = "B"
    regime_name = "Bottleneck Easing, ROI Holding"
    summary = "Market is confident in ROI but value is shifting from pure GPU beta toward ASICs, networking, and platforms."
elif bottleneck_score >= h and demand_score < h and stress_score >= h:
    regime = "C"
    regime_name = "Hardware Late-Cycle Squeeze"
    summary = "Dangerous late-cycle setup. Hardware scarcity rewarded, but platform/customer ROI is being questioned."
elif demand_score < l and bottleneck_score < l and stress_score >= h:
    regime = "D"
    regime_name = "CAPEX Bubble Fear"
    summary = "Falling confidence in AI CAPEX returns. High-beta infrastructure and long-duration hardware plays are vulnerable."

# Construct Output Payload
latest_date = pivot_df.index[-1].strftime('%Y-%m-%d')
output = {
    "date": latest_date,
    "last_updated_utc": datetime.now(timezone.utc).isoformat(),
    "regime": regime,
    "regime_name": regime_name,
    "summary": summary,
    "scores": {
        "demand": round(demand_score, 1),
        "bottleneck": round(bottleneck_score, 1),
        "substitution": round(substitution_score, 1),
        "stress": round(stress_score, 1),
        "breadth": round(breadth_score, 1)
    },
    "key_ratios": {
        "NVDA_QQQ_20D": round((get_return('NVDA', 20) - get_return('QQQ', 20)) * 100, 2),
        "TSM_SMH_20D": round((get_return('TSM', 20) - get_return('SMH', 20)) * 100, 2),
        "AVGO_NVDA_20D": round((get_return('AVGO', 20) - get_return('NVDA', 20)) * 100, 2),
        "HYG_LQD_20D": round(credit_ratio * 100, 2)
    },
    "warnings": warnings
}

with open('data/latest.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"Scoring complete. Regime classified as: {regime_name}")
