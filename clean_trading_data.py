import json
import glob
import re
import csv
import os
import time
import argparse
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Configuration
CONVERSIONS_DIR = "conversions"
OUTPUT_DIR = "cleaned_data"
PROGRESS_INTERVAL = 500  # Show progress every N files

# Thread-safe lock for updating shared data
data_lock = Lock()

# Pre-compile regex patterns for performance
POSITION_PATTERN = re.compile(
    r"\{'symbol':\s*'(\w+)',\s*'quantity':\s*([-\d.]+),\s*'entry_price':\s*([-\d.]+),\s*'current_price':\s*([-\d.]+),.*?'unrealized_pnl':\s*([-\d.]+),\s*'leverage':\s*(\d+)"
)
RETURN_PATTERN = re.compile(r"Current Total Return.*?:\s*([-\d.]+)%")
ACCOUNT_VALUE_PATTERN = re.compile(r"\*\*Current Account Value:\*\*\s*([\d.]+)")
AVAILABLE_CASH_PATTERN = re.compile(r"Available Cash:\s*([\d.]+)")
SHARPE_PATTERN = re.compile(r"Sharpe Ratio:\s*([-\d.]+)")


def extract_positions_from_prompt(user_prompt: str) -> Dict[str, Dict[str, Any]]:
    """Extract position information from user_prompt text"""
    positions = {}

    for match in POSITION_PATTERN.finditer(user_prompt):
        symbol = match.group(1)
        quantity = float(match.group(2))
        entry_price = float(match.group(3))
        current_price = float(match.group(4))
        unrealized_pnl = float(match.group(5))
        leverage = int(match.group(6))

        positions[symbol] = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "leverage": leverage,
        }

    return positions


def extract_account_info(user_prompt: str) -> Dict[str, Any]:
    """Extract account information from user_prompt"""
    info = {}

    match = RETURN_PATTERN.search(user_prompt)
    if match:
        info["return_pct"] = float(match.group(1))

    match = ACCOUNT_VALUE_PATTERN.search(user_prompt)
    if match:
        info["account_value"] = float(match.group(1))

    match = AVAILABLE_CASH_PATTERN.search(user_prompt)
    if match:
        info["available_cash"] = float(match.group(1))

    match = SHARPE_PATTERN.search(user_prompt)
    if match:
        info["sharpe_ratio"] = float(match.group(1))

    return info


def classify_change_type(prev_qty: float, curr_qty: float) -> str:
    """Classify the type of position change"""
    if prev_qty == 0 and curr_qty != 0:
        return "open_position"
    elif prev_qty != 0 and curr_qty == 0:
        return "close_position"
    elif (prev_qty > 0 and curr_qty < 0) or (prev_qty < 0 and curr_qty > 0):
        return "flip_position"
    elif abs(curr_qty) > abs(prev_qty):
        return "add_position"
    else:
        return "reduce_position"


def detect_position_changes(prev_positions: Dict, curr_positions: Dict) -> List[Dict]:
    """Detect changes between two position states"""
    changes = []

    all_symbols = set(prev_positions.keys()) | set(curr_positions.keys())

    for symbol in all_symbols:
        prev_qty = prev_positions.get(symbol, {}).get("quantity", 0)
        curr_qty = curr_positions.get(symbol, {}).get("quantity", 0)

        # Check if quantity changed (with tolerance for floating point errors)
        if abs(curr_qty - prev_qty) > 0.01:
            change_type = classify_change_type(prev_qty, curr_qty)

            changes.append(
                {
                    "symbol": symbol,
                    "prev_quantity": prev_qty,
                    "curr_quantity": curr_qty,
                    "change_type": change_type,
                    "position_details": curr_positions.get(symbol, {}),
                }
            )

    return changes


def process_single_file(filepath: str) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
    """Process a single JSON file and extract conversations"""
    local_conversations = defaultdict(list)
    errors = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        conversations = data.get("conversations", [])

        for conv in conversations:
            model_id = conv.get("model_id")
            if not model_id:
                continue

            # Extract positions and account info
            user_prompt = conv.get("user_prompt", "")
            positions = extract_positions_from_prompt(user_prompt)
            account_info = extract_account_info(user_prompt)

            # Only keep records with valid data
            if account_info.get("account_value"):
                local_conversations[model_id].append(
                    {
                        "timestamp": conv.get("timestamp"),
                        "cycle_id": conv.get("cycle_id"),
                        "model_id": model_id,
                        "positions": positions,
                        "account_info": account_info,
                        "cot_trace": conv.get("cot_trace", ""),
                        "cot_trace_summary": conv.get("cot_trace_summary", ""),
                        "llm_response": conv.get("llm_response", {}),
                    }
                )

    except Exception as e:
        errors.append({"file": filepath, "error": str(e)})

    return dict(local_conversations), errors


def print_progress_bar(
    completed: int, total: int, bar_length: int = 50, start_time: float = None
):
    """Print a progress bar"""
    percent = completed / total
    filled = int(bar_length * percent)
    bar = "█" * filled + "-" * (bar_length - filled)

    elapsed = time.time() - start_time if start_time else 0
    rate = completed / elapsed if elapsed > 0 else 0
    remaining = (total - completed) / rate if rate > 0 else 0

    print(
        f"\r[{bar}] {completed:,}/{total:,} ({percent*100:.1f}%) | "
        f"{rate:.1f} files/sec | ETA: {remaining/60:.1f} min",
        end="",
        flush=True,
    )


def load_all_conversations(
    num_threads: int = 4,
) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
    """Load and organize all conversation data by model_id using parallel processing"""
    print("=" * 60)
    print("LOADING ALL CONVERSATION DATA")
    print("=" * 60)

    all_files = sorted(glob.glob(f"{CONVERSIONS_DIR}/*.json"))
    total_files = len(all_files)

    print(f"Found {total_files:,} JSON files")
    print(f"Using {num_threads} threads for parallel processing")
    print(f"Starting to process...")
    print()

    model_conversations = defaultdict(list)
    error_files = []
    total_conversations = 0
    completed_files = 0

    start_time = time.time()

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(process_single_file, filepath): filepath
            for filepath in all_files
        }

        # Process completed tasks
        for future in as_completed(future_to_file):
            completed_files += 1

            # Get results
            local_convs, local_errors = future.result()

            # Thread-safe merge into global data structures
            with data_lock:
                for model_id, convs in local_convs.items():
                    model_conversations[model_id].extend(convs)
                    total_conversations += len(convs)

                error_files.extend(local_errors)

            # Update progress bar
            if (
                completed_files % PROGRESS_INTERVAL == 0
                or completed_files == total_files
            ):
                print_progress_bar(completed_files, total_files, start_time=start_time)

    # Final progress bar update
    print_progress_bar(total_files, total_files, start_time=start_time)
    print()  # New line after progress bar

    # Sort each model's conversations by timestamp
    print("\nSorting conversations by timestamp...")
    for model_id in model_conversations:
        model_conversations[model_id].sort(key=lambda x: x["timestamp"])

    elapsed_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("LOADING COMPLETE")
    print("=" * 60)
    print(f"Total files processed: {total_files:,}")
    print(f"Total conversations loaded: {total_conversations:,}")
    print(f"Processing time: {elapsed_time/60:.1f} minutes")
    print(f"Processing rate: {total_files/elapsed_time:.1f} files/sec")
    print(f"Error files: {len(error_files)}")
    print(f"\nConversations by model:")
    for model_id, convs in sorted(model_conversations.items()):
        print(f"  - {model_id}: {len(convs):,} records")

    return dict(model_conversations), error_files


def extract_trades(model_conversations: Dict[str, List[Dict]]) -> Tuple[Dict, List]:
    """Extract actual trades from conversation data"""
    print("\n" + "=" * 60)
    print("EXTRACTING TRADES")
    print("=" * 60)

    model_trades = defaultdict(list)
    all_trades_list = []

    for model_id, conversations in model_conversations.items():
        print(f"\nProcessing {model_id}...")
        print(f"  Total records: {len(conversations):,}")

        if len(conversations) < 2:
            print(f"  Skipping (insufficient data)")
            continue

        trades_found = 0

        for i in range(1, len(conversations)):
            prev_conv = conversations[i - 1]
            curr_conv = conversations[i]

            # Detect position changes
            changes = detect_position_changes(
                prev_conv["positions"], curr_conv["positions"]
            )

            if changes:
                trades_found += 1

                trade_record = {
                    "trade_id": f"{model_id}_{curr_conv['cycle_id']}",
                    "model_id": model_id,
                    "timestamp": curr_conv["timestamp"],
                    "cycle_id": curr_conv["cycle_id"],
                    "prev_cycle_id": prev_conv["cycle_id"],
                    # Position changes
                    "position_changes": changes,
                    "positions_before": prev_conv["positions"],
                    "positions_after": curr_conv["positions"],
                    # Account info
                    "account_info": curr_conv["account_info"],
                    "prev_account_value": prev_conv["account_info"].get(
                        "account_value"
                    ),
                    "curr_account_value": curr_conv["account_info"].get(
                        "account_value"
                    ),
                    # Decision data
                    "llm_response": curr_conv["llm_response"],
                    "cot_trace": curr_conv["cot_trace"],
                    "cot_trace_summary": curr_conv["cot_trace_summary"],
                }

                model_trades[model_id].append(trade_record)
                all_trades_list.append(trade_record)

        print(f"  Trades detected: {trades_found:,}")

    print("\n" + "=" * 60)
    print("TRADE EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Total trades extracted: {len(all_trades_list):,}")
    print("\nTrades by model:")
    for model_id, trades in sorted(model_trades.items(), key=lambda x: -len(x[1])):
        print(f"  - {model_id}: {len(trades):,} trades")

    return dict(model_trades), all_trades_list


def save_cleaned_data(model_trades: Dict, all_trades: List, error_files: List):
    """Save cleaned data to files"""
    print("\n" + "=" * 60)
    print("SAVING CLEANED DATA")
    print("=" * 60)

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Save each model's trades to separate JSON files
    for model_id, trades in model_trades.items():
        filepath = os.path.join(OUTPUT_DIR, f"{model_id}_trades.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(trades, f, ensure_ascii=False, indent=2)
        print(f"Saved: {filepath} ({len(trades):,} trades)")

    # 2. Save trade index CSV
    csv_path = os.path.join(OUTPUT_DIR, "trades_index.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Trade ID",
                "Model",
                "Cycle ID",
                "Timestamp",
                "Changes",
                "Account Value",
                "Return %",
                "Summary",
            ]
        )

        for trade in all_trades:
            changes_str = "; ".join(
                [
                    f"{c['symbol']}:{c['prev_quantity']:.2f}->{c['curr_quantity']:.2f}({c['change_type']})"
                    for c in trade["position_changes"]
                ]
            )

            writer.writerow(
                [
                    trade["trade_id"],
                    trade["model_id"],
                    trade["cycle_id"],
                    trade["timestamp"],
                    changes_str,
                    trade["curr_account_value"],
                    trade["account_info"].get("return_pct", 0),
                    trade["cot_trace_summary"][:100],
                ]
            )

    print(f"Saved: {csv_path}")

    # 3. Save cleaning summary
    summary = {
        "cleaning_timestamp": datetime.now().isoformat(),
        "total_trades": len(all_trades),
        "trades_by_model": {
            model_id: len(trades) for model_id, trades in model_trades.items()
        },
        "error_files_count": len(error_files),
        "error_files": (
            error_files[:100] if error_files else []
        ),  # Save first 100 errors
    }

    summary_path = os.path.join(OUTPUT_DIR, "cleaning_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved: {summary_path}")

    # Calculate file sizes
    print("\n" + "=" * 60)
    print("DATA SIZE SUMMARY")
    print("=" * 60)

    total_size = 0
    for filename in os.listdir(OUTPUT_DIR):
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            total_size += size
            print(f"{filename}: {size / 1024 / 1024:.2f} MB")

    print(f"\nTotal cleaned data size: {total_size / 1024 / 1024:.2f} MB")
    print(f"Original data size (estimated): ~83 GB")
    print(
        f"Compression ratio: {(1 - total_size / (83 * 1024 * 1024 * 1024)) * 100:.2f}%"
    )


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Clean trading data by extracting actual trades from conversation logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python clean_trading_data.py                    # Use default 4 threads
  python clean_trading_data.py --threads 8        # Use 8 threads
  python clean_trading_data.py --threads 1        # Single-threaded processing
        """,
    )

    parser.add_argument(
        "--threads",
        "-t",
        type=int,
        default=4,
        help="Number of threads for parallel processing (default: 4)",
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=CONVERSIONS_DIR,
        help=f"Input directory containing JSON files (default: {CONVERSIONS_DIR})",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=OUTPUT_DIR,
        help=f"Output directory for cleaned data (default: {OUTPUT_DIR})",
    )

    return parser.parse_args()


def main():
    """Main execution function"""
    # Parse command line arguments
    args = parse_arguments()

    # Update global configuration
    global CONVERSIONS_DIR, OUTPUT_DIR
    CONVERSIONS_DIR = args.input
    OUTPUT_DIR = args.output

    print("=" * 60)
    print("FULL TRADING DATA CLEANING PIPELINE")
    print("=" * 60)
    print(f"Input directory: {CONVERSIONS_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Threads: {args.threads}")
    print("=" * 60)

    overall_start = time.time()

    try:
        # Step 1: Load all conversations (with parallel processing)
        model_conversations, error_files = load_all_conversations(
            num_threads=args.threads
        )

        # Step 2: Extract trades
        model_trades, all_trades = extract_trades(model_conversations)

        # Step 3: Save cleaned data
        save_cleaned_data(model_trades, all_trades, error_files)

        overall_time = time.time() - overall_start

        print("\n" + "=" * 60)
        print("CLEANING COMPLETE!")
        print("=" * 60)
        print(f"Total execution time: {overall_time/60:.1f} minutes")
        print(
            f"Average processing rate: {len(glob.glob(f'{CONVERSIONS_DIR}/*.json'))/overall_time:.1f} files/sec"
        )
        print(f"Total trades extracted: {len(all_trades):,}")
        print(f"Output location: {OUTPUT_DIR}/")
        print("\nNext steps:")
        print("1. Review cleaned data files")
        print("2. Generate analysis report")
        print("3. Proceed with trading strategy analysis")

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        print("Partial results may be incomplete")
    except Exception as e:
        print(f"\nERROR during processing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
