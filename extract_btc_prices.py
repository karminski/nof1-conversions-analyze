import json
import os
from datetime import datetime
from collections import defaultdict

# Configuration
CLEANED_DATA_DIR = "cleaned_data"
OUTPUT_FILE = "btc_price_data.json"


def load_all_trades():
    """Load all trades from all models"""
    all_trades = []
    
    models = [
        "qwen3-max",
        "deepseek-chat-v3.1",
        "claude-sonnet-4-5",
        "grok-4",
        "gemini-2.5-pro",
        "gpt-5"
    ]
    
    for model_id in models:
        filepath = os.path.join(CLEANED_DATA_DIR, f"{model_id}_trades.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                trades = json.load(f)
                all_trades.extend(trades)
        except Exception as e:
            print(f"Error loading {model_id}: {e}")
    
    return all_trades


def extract_btc_prices(trades):
    """Extract BTC prices from trade data"""
    btc_prices = []
    
    for trade in trades:
        timestamp = trade.get("timestamp", 0)
        
        # Check positions_before
        positions_before = trade.get("positions_before", {})
        if "BTC" in positions_before:
            btc_data = positions_before["BTC"]
            price = btc_data.get("current_price", 0)
            if price > 0:
                btc_prices.append({
                    "timestamp": timestamp,
                    "price": price,
                    "source": "positions_before"
                })
        
        # Check positions_after
        positions_after = trade.get("positions_after", {})
        if "BTC" in positions_after:
            btc_data = positions_after["BTC"]
            price = btc_data.get("current_price", 0)
            if price > 0:
                btc_prices.append({
                    "timestamp": timestamp,
                    "price": price,
                    "source": "positions_after"
                })
        
        # Check position_changes
        for change in trade.get("position_changes", []):
            if change.get("symbol") == "BTC":
                pos_details = change.get("position_details", {})
                price = pos_details.get("current_price", 0)
                if price > 0:
                    btc_prices.append({
                        "timestamp": timestamp,
                        "price": price,
                        "source": "position_changes"
                    })
    
    # Remove duplicates and sort by timestamp
    unique_prices = {}
    for entry in btc_prices:
        ts = entry["timestamp"]
        if ts not in unique_prices:
            unique_prices[ts] = entry
    
    sorted_prices = sorted(unique_prices.values(), key=lambda x: x["timestamp"])
    
    print(f"Extracted {len(sorted_prices)} unique BTC price points")
    
    return sorted_prices


def aggregate_to_daily_candles(price_points):
    """Aggregate price points into daily candles"""
    daily_data = defaultdict(list)
    
    for point in price_points:
        timestamp = point["timestamp"]
        date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
        daily_data[date].append(point["price"])
    
    candles = []
    for date, prices in sorted(daily_data.items()):
        if prices:
            candles.append({
                "date": date,
                "timestamp": datetime.strptime(date, '%Y-%m-%d').timestamp(),
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "count": len(prices)
            })
    
    print(f"Generated {len(candles)} daily candles")
    
    return candles


def main():
    print("=" * 60)
    print("EXTRACTING BTC PRICE DATA")
    print("=" * 60)
    
    # Load trades
    trades = load_all_trades()
    print(f"Loaded {len(trades)} trades")
    
    # Extract BTC prices
    btc_prices = extract_btc_prices(trades)
    
    # Aggregate to daily candles
    daily_candles = aggregate_to_daily_candles(btc_prices)
    
    # Save to JSON
    output_data = {
        "raw_prices": btc_prices,
        "daily_candles": daily_candles
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nBTC price data saved to: {OUTPUT_FILE}")
    
    # Print summary
    if daily_candles:
        print(f"\nDate range: {daily_candles[0]['date']} to {daily_candles[-1]['date']}")
        print(f"Price range: ${daily_candles[0]['open']:.2f} - ${max(c['high'] for c in daily_candles):.2f}")
    
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()

