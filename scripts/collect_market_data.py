import json
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

# Load Config Safely
try:
    with open('config/tickers.json', 'r') as f:
        baskets = json.load(f)
except Exception as e:
    print(f"Error loading tickers.json: {e}")
    baskets = {}

# Flatten unique tickers
all_tickers = set()
for basket in baskets.values():
    all_tickers.update(basket)
all_tickers = list(all_tickers)

os.makedirs('data', exist_ok=True)
warnings = []
price_data = []
failed_tickers = []

print(f"Starting market data collection. Expected ticker count: {len(all_tickers)}")

for ticker in all_tickers:
    try:
        data = yf.Ticker(ticker).history(period="1y")
        if data.empty:
            warnings.append({"ticker": ticker, "issue": "No data returned"})
            failed_tickers.append(ticker)
            continue
            
        data.reset_index(inplace=True)
        for _, row in data.iterrows():
            price_data.append({
                "date": row['Date'].strftime('%Y-%m-%d'),
                "ticker": ticker,
                "close": row['Close'],
                "volume": row['Volume']
            })
    except Exception as e:
        warnings.append({"ticker": ticker, "issue": str(e)})
        failed_tickers.append(ticker)

df = pd.DataFrame(price_data)
if not df.empty:
    df.to_csv('data/raw_prices.csv', index=False)
else:
    print("Warning: raw_prices.csv is completely empty. YFinance may be blocking requests.")
    # Create empty CSV with headers so downstream doesn't fully break
    pd.DataFrame(columns=['date', 'ticker', 'close', 'volume']).to_csv('data/raw_prices.csv', index=False)

with open('data/warnings.json', 'w') as f:
    json.dump(warnings, f)

# Save explicit retrieval stats for today's run
retrieved_count = len(all_tickers) - len(failed_tickers)
retrieval_stats = {
    "expected_tickers": len(all_tickers),
    "retrieved_tickers": retrieved_count,
    "failed_tickers": failed_tickers
}
with open('data/retrieval_stats.json', 'w') as f:
    json.dump(retrieval_stats, f)

print(f"--- Data Collection Summary ---")
print(f"Expected Tickers : {len(all_tickers)}")
print(f"Retrieved Tickers: {retrieved_count}")
print(f"Failed Tickers   : {len(failed_tickers)} -> {failed_tickers}")
print("Market data collection complete.")
