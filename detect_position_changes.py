import json
import glob
import re
from collections import defaultdict
import csv

# 配置
CONVERSIONS_DIR = "conversions"
OUTPUT_DIR = "analysis_output"


def extract_positions_from_prompt(user_prompt):
    """从user_prompt中提取持仓信息"""
    positions = {}

    # 提取持仓信息的正则模式
    position_pattern = r"\{'symbol':\s*'(\w+)',\s*'quantity':\s*([-\d.]+),\s*'entry_price':\s*([-\d.]+),\s*'current_price':\s*([-\d.]+),.*?'unrealized_pnl':\s*([-\d.]+),\s*'leverage':\s*(\d+)"

    for match in re.finditer(position_pattern, user_prompt):
        symbol = match.group(1)
        quantity = float(match.group(2))
        entry_price = float(match.group(3))
        current_price = float(match.group(4))
        unrealized_pnl = float(match.group(5))
        leverage = int(match.group(6))

        positions[symbol] = {
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "leverage": leverage,
            "direction": "long" if quantity > 0 else "short",
        }

    return positions


def detect_position_changes(model_data):
    """检测持仓变化"""
    print(f"\n检测 {len(model_data)} 个模型的持仓变化...")

    all_changes = []

    for model_id, data_points in model_data.items():
        print(f"\n分析 {model_id}...")

        prev_positions = {}

        for i, point in enumerate(data_points):
            current_positions = point.get("positions", {})

            # 检测变化
            changes = compare_positions(
                prev_positions, current_positions, model_id, point
            )

            all_changes.extend(changes)
            prev_positions = current_positions

        print(
            f"  发现 {len([c for c in all_changes if c['model_id'] == model_id])} 个持仓变化"
        )

    return all_changes


def compare_positions(prev_positions, current_positions, model_id, point):
    """比较两个时间点的持仓差异"""
    changes = []

    # 获取所有涉及的币种
    all_coins = set(prev_positions.keys()) | set(current_positions.keys())

    for coin in all_coins:
        prev_pos = prev_positions.get(coin)
        curr_pos = current_positions.get(coin)

        # 新开仓
        if prev_pos is None and curr_pos is not None:
            change_type = "open_long" if curr_pos["quantity"] > 0 else "open_short"
            changes.append(
                {
                    "model_id": model_id,
                    "cycle_id": point["cycle_id"],
                    "timestamp": point["timestamp"],
                    "change_type": change_type,
                    "coin": coin,
                    "prev_quantity": 0,
                    "new_quantity": curr_pos["quantity"],
                    "leverage": curr_pos.get("leverage", "N/A"),
                    "entry_price": curr_pos.get("entry_price", 0),
                    "account_value": point["account_info"].get("account_value", 0),
                    "return_pct": point["account_info"].get("return_pct", 0),
                    "cot_trace": point.get("cot_trace", ""),
                    "cot_trace_summary": point.get("cot_trace_summary", ""),
                    "llm_response": point.get("llm_response", {}),
                }
            )

        # 平仓
        elif prev_pos is not None and curr_pos is None:
            change_type = "close_long" if prev_pos["quantity"] > 0 else "close_short"
            changes.append(
                {
                    "model_id": model_id,
                    "cycle_id": point["cycle_id"],
                    "timestamp": point["timestamp"],
                    "change_type": change_type,
                    "coin": coin,
                    "prev_quantity": prev_pos["quantity"],
                    "new_quantity": 0,
                    "leverage": prev_pos.get("leverage", "N/A"),
                    "entry_price": prev_pos.get("entry_price", 0),
                    "account_value": point["account_info"].get("account_value", 0),
                    "return_pct": point["account_info"].get("return_pct", 0),
                    "cot_trace": point.get("cot_trace", ""),
                    "cot_trace_summary": point.get("cot_trace_summary", ""),
                    "llm_response": point.get("llm_response", {}),
                }
            )

        # 加仓/减仓/翻转
        elif prev_pos is not None and curr_pos is not None:
            prev_qty = prev_pos["quantity"]
            curr_qty = curr_pos["quantity"]

            # 数量有变化
            if abs(curr_qty - prev_qty) > 0.01:  # 容忍小误差
                # 判断变化类型
                if (prev_qty > 0 and curr_qty > 0) or (prev_qty < 0 and curr_qty < 0):
                    # 同向变化：加仓或减仓
                    if abs(curr_qty) > abs(prev_qty):
                        change_type = "add_position"
                    else:
                        change_type = "reduce_position"
                else:
                    # 方向改变：翻转
                    change_type = "flip_position"

                changes.append(
                    {
                        "model_id": model_id,
                        "cycle_id": point["cycle_id"],
                        "timestamp": point["timestamp"],
                        "change_type": change_type,
                        "coin": coin,
                        "prev_quantity": prev_qty,
                        "new_quantity": curr_qty,
                        "leverage": curr_pos.get("leverage", "N/A"),
                        "entry_price": curr_pos.get("entry_price", 0),
                        "account_value": point["account_info"].get("account_value", 0),
                        "return_pct": point["account_info"].get("return_pct", 0),
                        "cot_trace": point.get("cot_trace", ""),
                        "cot_trace_summary": point.get("cot_trace_summary", ""),
                        "llm_response": point.get("llm_response", {}),
                    }
                )

    return changes


def load_model_data_with_positions():
    """加载数据并提取持仓信息"""
    print("加载数据并提取持仓信息...")

    files = sorted(glob.glob(f"{CONVERSIONS_DIR}/*.json"))
    print(f"找到 {len(files)} 个数据文件")

    model_data = defaultdict(list)

    for idx, filepath in enumerate(files, 1):
        if idx % 50 == 0:
            print(f"  处理进度: {idx}/{len(files)}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            conversations = data.get("conversations", [])

            for conv in conversations:
                model_id = conv.get("model_id")
                timestamp = conv.get("timestamp")
                cycle_id = conv.get("cycle_id")
                user_prompt = conv.get("user_prompt", "")

                # 提取账户信息
                account_info = {}
                match = re.search(r"Current Total Return.*?:\s*([-\d.]+)%", user_prompt)
                if match:
                    account_info["return_pct"] = float(match.group(1))

                match = re.search(
                    r"\*\*Current Account Value:\*\*\s*([\d.]+)", user_prompt
                )
                if match:
                    account_info["account_value"] = float(match.group(1))

                # 提取持仓信息
                positions = extract_positions_from_prompt(user_prompt)

                if account_info.get("account_value"):
                    model_data[model_id].append(
                        {
                            "timestamp": timestamp,
                            "cycle_id": cycle_id,
                            "account_info": account_info,
                            "positions": positions,
                            "cot_trace": conv.get("cot_trace", ""),
                            "cot_trace_summary": conv.get("cot_trace_summary", ""),
                            "llm_response": conv.get("llm_response", {}),
                        }
                    )
        except Exception as e:
            print(f"  处理文件 {filepath} 时出错: {e}")

    # 按时间排序
    for model_id in model_data:
        model_data[model_id].sort(key=lambda x: x["timestamp"])

    print(f"[OK] 数据加载完成，共 {len(model_data)} 个模型")
    return model_data


def export_changes_to_csv(changes):
    """导出持仓变化到CSV"""
    output_file = f"{OUTPUT_DIR}/position_changes.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Model",
                "Cycle ID",
                "Timestamp",
                "Change Type",
                "Coin",
                "Prev Quantity",
                "New Quantity",
                "Leverage",
                "Entry Price",
                "Account Value",
                "Return %",
                "COT Summary",
            ]
        )

        for change in sorted(changes, key=lambda x: (x["model_id"], x["timestamp"])):
            writer.writerow(
                [
                    change["model_id"],
                    change["cycle_id"],
                    change["timestamp"],
                    change["change_type"],
                    change["coin"],
                    f"{change['prev_quantity']:.2f}",
                    f"{change['new_quantity']:.2f}",
                    change["leverage"],
                    f"{change['entry_price']:.2f}",
                    f"{change['account_value']:.2f}",
                    f"{change['return_pct']:.2f}",
                    change["cot_trace_summary"][:200],
                ]
            )

    print(f"[OK] 持仓变化已保存: {output_file}")


def export_changes_to_json(changes):
    """导出详细的决策数据到JSON"""
    output_file = f"{OUTPUT_DIR}/trading_decisions.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(changes, f, ensure_ascii=False, indent=2)

    print(f"[OK] 详细决策数据已保存: {output_file}")


def analyze_changes_summary(changes):
    """分析持仓变化统计"""
    print("\n" + "=" * 60)
    print("持仓变化统计汇总")
    print("=" * 60)

    # 按模型统计
    model_stats = defaultdict(lambda: defaultdict(int))

    for change in changes:
        model_id = change["model_id"]
        change_type = change["change_type"]
        model_stats[model_id][change_type] += 1
        model_stats[model_id]["total"] += 1

    for model_id in sorted(model_stats.keys()):
        stats = model_stats[model_id]
        print(f"\n{model_id}:")
        print(f"  总交易次数: {stats['total']}")
        for change_type in [
            "open_long",
            "open_short",
            "close_long",
            "close_short",
            "add_position",
            "reduce_position",
            "flip_position",
        ]:
            if stats[change_type] > 0:
                print(f"  {change_type}: {stats[change_type]}")


def main():
    print("=" * 60)
    print("持仓变化检测与分析")
    print("=" * 60)

    # 加载数据
    model_data = load_model_data_with_positions()

    # 检测变化
    changes = detect_position_changes(model_data)

    # 统计分析
    analyze_changes_summary(changes)

    # 导出数据
    export_changes_to_csv(changes)
    export_changes_to_json(changes)

    print("\n" + "=" * 60)
    print(f"[SUCCESS] 分析完成！共检测到 {len(changes)} 个持仓变化")
    print("=" * 60)

    return changes, model_data


if __name__ == "__main__":
    main()
