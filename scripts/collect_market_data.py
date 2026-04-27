import json
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

# Load Config
with open('config/tickers.json', 'r') as f:
    baskets = json.load(f)

# Flatten unique tickers
all_tickers = set()
for basket in baskets.values():
    all_tickers.update(basket)
all_tickers = list(all_tickers)

os.makedirs('data', exist_ok=True)
warnings = []
price_data = []

print(f"Fetching data for {len(all_tickers)} tickers...")

for ticker in all_tickers:
    try:
        data = yf.Ticker(ticker).history(period="1y")
        if data.empty:
            warnings.append({"ticker": ticker, "issue": "No data returned"})
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

df = pd.DataFrame(price_data)
df.to_csv('data/raw_prices.csv', index=False)

with open('data/warnings.json', 'w') as f:
    json.dump(warnings, f)

print("Market data collection complete.")
