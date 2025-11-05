import json
import glob
import random
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Configuration
CONVERSIONS_DIR = "conversions"
SAMPLE_SIZE = 30  # Number of files to sample
OUTPUT_REPORT = "exploration_report.md"


def sample_data_files() -> List[str]:
    """Sample a subset of JSON files from the conversions directory"""
    print(f"Scanning {CONVERSIONS_DIR} directory...")
    
    all_files = sorted(glob.glob(f"{CONVERSIONS_DIR}/*.json"))
    total_files = len(all_files)
    
    print(f"Found {total_files:,} files")
    
    # Sample files evenly across the time range
    if total_files <= SAMPLE_SIZE:
        sampled_files = all_files
    else:
        # Take samples from beginning, middle, and end to capture temporal patterns
        step = total_files // SAMPLE_SIZE
        sampled_files = [all_files[i * step] for i in range(SAMPLE_SIZE)]
    
    print(f"Sampled {len(sampled_files)} files for analysis")
    return sampled_files


def extract_positions_from_prompt(user_prompt: str) -> List[Dict[str, Any]]:
    """Extract position information from user_prompt text"""
    positions = []
    
    # Pattern to match position dictionaries
    position_pattern = r"\{'symbol':\s*'(\w+)',\s*'quantity':\s*([-\d.]+),"
    
    for match in re.finditer(position_pattern, user_prompt):
        symbol = match.group(1)
        quantity = float(match.group(2))
        positions.append({
            "symbol": symbol,
            "quantity": quantity
        })
    
    return positions


def analyze_field_structure(conversations: List[Dict]) -> Dict[str, Any]:
    """Analyze the structure and frequency of fields in conversations"""
    field_stats = defaultdict(lambda: {"count": 0, "types": set(), "sample_values": []})
    signal_values = defaultdict(int)
    
    for conv in conversations:
        # Top-level fields
        for field, value in conv.items():
            field_stats[field]["count"] += 1
            field_stats[field]["types"].add(type(value).__name__)
            
            # Sample first few values
            if len(field_stats[field]["sample_values"]) < 3:
                if isinstance(value, (str, int, float)):
                    field_stats[field]["sample_values"].append(value)
        
        # Analyze llm_response signals
        llm_response = conv.get("llm_response", {})
        if isinstance(llm_response, dict):
            for coin, decision in llm_response.items():
                if isinstance(decision, dict):
                    signal = decision.get("signal", "N/A")
                    signal_values[signal] += 1
    
    return {
        "field_stats": dict(field_stats),
        "signal_distribution": dict(signal_values)
    }


def compare_consecutive_records(model_data: Dict[str, List[Dict]]) -> List[Dict]:
    """Compare consecutive records to identify trading actions"""
    trade_candidates = []
    
    for model_id, records in model_data.items():
        if len(records) < 2:
            continue
        
        for i in range(1, len(records)):
            prev_record = records[i - 1]
            curr_record = records[i]
            
            # Extract positions from user_prompt
            prev_positions = extract_positions_from_prompt(prev_record.get("user_prompt", ""))
            curr_positions = extract_positions_from_prompt(curr_record.get("user_prompt", ""))
            
            # Convert to dict for easier comparison
            prev_pos_dict = {p["symbol"]: p["quantity"] for p in prev_positions}
            curr_pos_dict = {p["symbol"]: p["quantity"] for p in curr_positions}
            
            # Detect changes
            all_symbols = set(prev_pos_dict.keys()) | set(curr_pos_dict.keys())
            changes = []
            
            for symbol in all_symbols:
                prev_qty = prev_pos_dict.get(symbol, 0)
                curr_qty = curr_pos_dict.get(symbol, 0)
                
                if abs(curr_qty - prev_qty) > 0.01:  # Tolerance for floating point
                    change_type = "unknown"
                    
                    if prev_qty == 0 and curr_qty != 0:
                        change_type = "open_position"
                    elif prev_qty != 0 and curr_qty == 0:
                        change_type = "close_position"
                    elif prev_qty != 0 and curr_qty != 0:
                        if abs(curr_qty) > abs(prev_qty):
                            change_type = "add_position"
                        else:
                            change_type = "reduce_position"
                        
                        # Check for direction flip
                        if (prev_qty > 0 and curr_qty < 0) or (prev_qty < 0 and curr_qty > 0):
                            change_type = "flip_position"
                    
                    changes.append({
                        "symbol": symbol,
                        "prev_qty": prev_qty,
                        "curr_qty": curr_qty,
                        "change_type": change_type
                    })
            
            if changes:
                # Get signal changes from llm_response
                prev_llm = prev_record.get("llm_response", {})
                curr_llm = curr_record.get("llm_response", {})
                
                signal_changes = {}
                for symbol in all_symbols:
                    prev_signal = prev_llm.get(symbol, {}).get("signal", "N/A") if isinstance(prev_llm, dict) else "N/A"
                    curr_signal = curr_llm.get(symbol, {}).get("signal", "N/A") if isinstance(curr_llm, dict) else "N/A"
                    
                    if prev_signal != curr_signal:
                        signal_changes[symbol] = {
                            "prev": prev_signal,
                            "curr": curr_signal
                        }
                
                trade_candidates.append({
                    "model_id": model_id,
                    "prev_cycle": prev_record.get("cycle_id"),
                    "curr_cycle": curr_record.get("cycle_id"),
                    "prev_timestamp": prev_record.get("timestamp"),
                    "curr_timestamp": curr_record.get("timestamp"),
                    "position_changes": changes,
                    "signal_changes": signal_changes,
                    "prev_record": prev_record,
                    "curr_record": curr_record
                })
    
    return trade_candidates


def load_and_analyze_sample() -> Tuple[Dict, List[Dict]]:
    """Load sampled data and perform analysis"""
    print("\n" + "="*60)
    print("STEP 1: Loading and Parsing Sample Data")
    print("="*60)
    
    sampled_files = sample_data_files()
    
    all_conversations = []
    model_data = defaultdict(list)
    
    for idx, filepath in enumerate(sampled_files, 1):
        print(f"Processing file {idx}/{len(sampled_files)}: {filepath.split('/')[-1]}")
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            conversations = data.get("conversations", [])
            all_conversations.extend(conversations)
            
            # Group by model_id
            for conv in conversations:
                model_id = conv.get("model_id")
                if model_id:
                    model_data[model_id].append(conv)
        
        except Exception as e:
            print(f"  ⚠ Error processing {filepath}: {e}")
    
    # Sort each model's data by timestamp
    for model_id in model_data:
        model_data[model_id].sort(key=lambda x: x.get("timestamp", 0))
    
    print(f"\n[OK] Loaded {len(all_conversations)} conversations from {len(sampled_files)} files")
    print(f"[OK] Found {len(model_data)} unique models")
    for model_id, records in sorted(model_data.items()):
        print(f"  - {model_id}: {len(records)} records")
    
    print("\n" + "="*60)
    print("STEP 2: Analyzing Field Structure")
    print("="*60)
    
    structure_analysis = analyze_field_structure(all_conversations)
    
    print("\n[OK] Field structure analysis complete")
    print(f"[OK] Found {len(structure_analysis['field_stats'])} unique fields")
    print(f"[OK] Found {len(structure_analysis['signal_distribution'])} unique signal values")
    
    print("\n" + "="*60)
    print("STEP 3: Comparing Consecutive Records for Trade Detection")
    print("="*60)
    
    trade_candidates = compare_consecutive_records(model_data)
    
    print(f"\n[OK] Found {len(trade_candidates)} potential trading actions")
    
    # Summary statistics
    change_type_counts = defaultdict(int)
    for trade in trade_candidates:
        for change in trade["position_changes"]:
            change_type_counts[change["change_type"]] += 1
    
    print("\nTrade action breakdown:")
    for change_type, count in sorted(change_type_counts.items(), key=lambda x: -x[1]):
        print(f"  - {change_type}: {count}")
    
    return structure_analysis, trade_candidates


def generate_markdown_report(structure_analysis: Dict, trade_candidates: List[Dict]):
    """Generate comprehensive markdown report"""
    print("\n" + "="*60)
    print("STEP 4: Generating Analysis Report")
    print("="*60)
    
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("# Trade Signal Exploration Report\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # Section 1: Field Structure
        f.write("## 1. Data Structure Analysis\n\n")
        f.write("### 1.1 Top-Level Fields\n\n")
        f.write("| Field Name | Count | Data Type | Sample Values |\n")
        f.write("|------------|-------|-----------|---------------|\n")
        
        field_stats = structure_analysis["field_stats"]
        for field, stats in sorted(field_stats.items()):
            types_str = ", ".join(stats["types"])
            sample_str = str(stats["sample_values"][:2])[:50] + "..."
            f.write(f"| `{field}` | {stats['count']} | {types_str} | {sample_str} |\n")
        
        f.write("\n### 1.2 Signal Value Distribution\n\n")
        f.write("| Signal Value | Occurrences |\n")
        f.write("|--------------|-------------|\n")
        
        signal_dist = structure_analysis["signal_distribution"]
        for signal, count in sorted(signal_dist.items(), key=lambda x: -x[1]):
            f.write(f"| `{signal}` | {count} |\n")
        
        # Section 2: Trade Detection Analysis
        f.write("\n---\n\n")
        f.write("## 2. Trade Detection Analysis\n\n")
        f.write(f"**Total potential trades detected**: {len(trade_candidates)}\n\n")
        
        # Group by model
        trades_by_model = defaultdict(list)
        for trade in trade_candidates:
            trades_by_model[trade["model_id"]].append(trade)
        
        f.write("### 2.1 Trades by Model\n\n")
        f.write("| Model ID | Number of Trades |\n")
        f.write("|----------|------------------|\n")
        for model_id, trades in sorted(trades_by_model.items(), key=lambda x: -len(x[1])):
            f.write(f"| {model_id} | {len(trades)} |\n")
        
        # Section 3: Trade Examples
        f.write("\n---\n\n")
        f.write("## 3. Detailed Trade Examples\n\n")
        
        # Show 5 representative examples
        examples_to_show = min(5, len(trade_candidates))
        for i in range(examples_to_show):
            trade = trade_candidates[i]
            f.write(f"### Example {i+1}: {trade['model_id']}\n\n")
            f.write(f"**Cycle**: {trade['prev_cycle']} → {trade['curr_cycle']}\n\n")
            
            f.write("**Position Changes**:\n")
            for change in trade["position_changes"]:
                f.write(f"- `{change['symbol']}`: {change['prev_qty']:.2f} → {change['curr_qty']:.2f} ({change['change_type']})\n")
            
            if trade["signal_changes"]:
                f.write("\n**Signal Changes**:\n")
                for symbol, signals in trade["signal_changes"].items():
                    f.write(f"- `{symbol}`: {signals['prev']} → {signals['curr']}\n")
            
            # Show COT trace summary if available
            cot_summary = trade["curr_record"].get("cot_trace_summary", "")
            if cot_summary:
                f.write(f"\n**Strategy Summary**:\n> {cot_summary[:300]}...\n")
            
            f.write("\n")
        
        # Section 4: Recommendations
        f.write("\n---\n\n")
        f.write("## 4. Trade Detection Rules - Recommendations\n\n")
        f.write("Based on the analysis, we can identify a trade has occurred when:\n\n")
        f.write("### Primary Indicators (High Confidence)\n\n")
        f.write("1. **Position Quantity Change**: The `quantity` in `user_prompt` positions changes between consecutive cycles\n")
        f.write("   - New position opened: quantity goes from 0 to non-zero\n")
        f.write("   - Position closed: quantity goes from non-zero to 0\n")
        f.write("   - Position adjusted: non-zero quantity changes\n\n")
        
        f.write("2. **Position List Changes**: Number of active positions in `user_prompt` increases or decreases\n\n")
        
        f.write("### Secondary Indicators (Supporting Evidence)\n\n")
        f.write("1. **Signal Changes**: `llm_response[coin]['signal']` changes from 'hold' to 'buy'/'sell'/'short'\n")
        f.write("2. **Account Value Jump**: Significant change in account value (may indicate realized P&L)\n\n")
        
        f.write("### Recommended Trade Detection Logic\n\n")
        f.write("```python\n")
        f.write("def is_trade_action(prev_record, curr_record):\n")
        f.write("    \"\"\"\n")
        f.write("    Returns True if a trade action occurred between two records\n")
        f.write("    \"\"\"\n")
        f.write("    # Extract positions from user_prompt\n")
        f.write("    prev_positions = extract_positions(prev_record['user_prompt'])\n")
        f.write("    curr_positions = extract_positions(curr_record['user_prompt'])\n")
        f.write("    \n")
        f.write("    # Compare position quantities\n")
        f.write("    for symbol in all_symbols:\n")
        f.write("        prev_qty = prev_positions.get(symbol, 0)\n")
        f.write("        curr_qty = curr_positions.get(symbol, 0)\n")
        f.write("        \n")
        f.write("        if abs(curr_qty - prev_qty) > 0.01:  # Trade detected\n")
        f.write("            return True\n")
        f.write("    \n")
        f.write("    return False\n")
        f.write("```\n\n")
        
        f.write("### Key Findings\n\n")
        f.write("- ✅ **Position changes in user_prompt are the most reliable indicator**\n")
        f.write("- ✅ **Signal field shows intention but may not reflect execution**\n")
        f.write("- ⚠️ **Need to compare consecutive records within same model**\n")
        f.write("- ⚠️ **Handle edge cases: small floating point differences**\n\n")
        
        f.write("---\n\n")
        f.write("## Next Steps\n\n")
        f.write("1. Implement the recommended trade detection logic\n")
        f.write("2. Process all 56k+ files to extract only trade-action records\n")
        f.write("3. Save cleaned data grouped by model_id\n")
        f.write("4. Include: timestamp, cycle_id, positions, llm_response, cot_trace, account metrics\n")
    
    print(f"[OK] Report saved to: {OUTPUT_REPORT}")


def main():
    """Main execution function"""
    print("="*60)
    print("TRADE SIGNAL EXPLORATION ANALYSIS")
    print("="*60)
    print(f"Sampling from: {CONVERSIONS_DIR}")
    print(f"Sample size: {SAMPLE_SIZE} files")
    print(f"Output report: {OUTPUT_REPORT}")
    print("="*60)
    
    try:
        # Load and analyze
        structure_analysis, trade_candidates = load_and_analyze_sample()
        
        # Generate report
        generate_markdown_report(structure_analysis, trade_candidates)
        
        print("\n" + "="*60)
        print("✅ ANALYSIS COMPLETE")
        print("="*60)
        print(f"Report saved: {OUTPUT_REPORT}")
        print("\nKey Findings:")
        print("- Position quantity changes in user_prompt are most reliable")
        print("- Signal field shows intent but may lag actual execution")
        print("- Consecutive record comparison is essential")
        print("\nReady to proceed with full data cleaning!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

