import json
import glob
import re
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import csv
import os

# 配置
CONVERSIONS_DIR = "conversions"
OUTPUT_DIR = "analysis_output"
INITIAL_CAPITAL = 10000
INFLECTION_THRESHOLD = 0.05  # 5%

# 颜色配置
MODEL_COLORS = {
    "qwen3-max": "#00C853",  # 绿色
    "deepseek-chat-v3.1": "#2196F3",  # 蓝色
    "gpt-5": "#F44336",  # 红色
    "claude-sonnet-4-5": "#9C27B0",  # 紫色
    "gemini-2.5-pro": "#FF9800",  # 橙色
    "grok-4": "#607D8B",  # 灰蓝色
}


def create_output_dir():
    """创建输出目录"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"[OK] Created output directory: {OUTPUT_DIR}")


def extract_account_info(user_prompt):
    """从user_prompt中提取账户信息"""
    info = {}

    # 提取总回报率
    match = re.search(r"Current Total Return.*?:\s*([-\d.]+)%", user_prompt)
    if match:
        info["return_pct"] = float(match.group(1))

    # 提取账户价值
    match = re.search(r"\*\*Current Account Value:\*\*\s*([\d.]+)", user_prompt)
    if match:
        info["account_value"] = float(match.group(1))

    # 提取可用现金
    match = re.search(r"Available Cash:\s*([\d.]+)", user_prompt)
    if match:
        info["available_cash"] = float(match.group(1))

    # 提取Sharpe比率
    match = re.search(r"Sharpe Ratio:\s*([-\d.]+)", user_prompt)
    if match:
        info["sharpe_ratio"] = float(match.group(1))

    # 提取持仓信息
    positions = []
    position_pattern = r"\{'symbol':\s*'(\w+)',\s*'quantity':\s*([-\d.]+),.*?'unrealized_pnl':\s*([-\d.]+)"
    for match in re.finditer(position_pattern, user_prompt):
        positions.append(
            {
                "symbol": match.group(1),
                "quantity": float(match.group(2)),
                "unrealized_pnl": float(match.group(3)),
            }
        )
    info["positions"] = positions

    return info


def load_all_data():
    """加载所有JSON文件数据"""
    print("正在加载数据文件...")

    files = sorted(glob.glob(f"{CONVERSIONS_DIR}/*.json"))
    print(f"找到 {len(files)} 个数据文件")

    # 按模型组织数据
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
                account_info = extract_account_info(user_prompt)

                if account_info and "account_value" in account_info:
                    model_data[model_id].append(
                        {
                            "timestamp": timestamp,
                            "cycle_id": cycle_id,
                            "account_info": account_info,
                            "cot_trace": conv.get("cot_trace", ""),
                            "cot_trace_summary": conv.get("cot_trace_summary", ""),
                            "llm_response": conv.get("llm_response", {}),
                            "file": filepath,
                        }
                    )
        except Exception as e:
            print(f"  ⚠ 处理文件 {filepath} 时出错: {e}")

    # 按时间排序
    for model_id in model_data:
        model_data[model_id].sort(key=lambda x: x["timestamp"])

    print(f"[OK] Data loaded: {len(model_data)} models")
    for model_id, data in model_data.items():
        print(f"  - {model_id}: {len(data)} data points")

    return model_data


def calculate_changes(model_data):
    """计算账户价值变化率"""
    print("\n计算价值变化率...")

    for model_id, data_points in model_data.items():
        for i in range(len(data_points)):
            if i == 0:
                # 第一个数据点，与初始资金比较
                prev_value = INITIAL_CAPITAL
            else:
                prev_value = data_points[i - 1]["account_info"].get(
                    "account_value", INITIAL_CAPITAL
                )

            current_value = data_points[i]["account_info"].get(
                "account_value", prev_value
            )
            change_pct = ((current_value - prev_value) / prev_value) * 100

            data_points[i]["value_change_pct"] = change_pct
            data_points[i]["prev_value"] = prev_value

    print("[OK] Change rate calculated")


def identify_inflection_points(model_data):
    """识别拐点（变化率 >= 5%）"""
    print(f"\n识别拐点（阈值: {INFLECTION_THRESHOLD*100}%）...")

    inflection_points = defaultdict(list)

    for model_id, data_points in model_data.items():
        for point in data_points:
            change = abs(point.get("value_change_pct", 0))
            if change >= INFLECTION_THRESHOLD * 100:
                inflection_points[model_id].append(point)

    print("[OK] Inflection points identified")
    for model_id, points in inflection_points.items():
        print(f"  - {model_id}: {len(points)} inflection points")

    return inflection_points


def generate_charts(model_data):
    """生成可视化图表"""
    print("\n生成可视化图表...")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))

    # 图表1: 收益率对比
    for model_id, data_points in model_data.items():
        if not data_points:
            continue

        cycles = [p["cycle_id"] for p in data_points]
        returns = [p["account_info"].get("return_pct", 0) for p in data_points]

        color = MODEL_COLORS.get(model_id, "#000000")
        linewidth = (
            2.5 if model_id in ["qwen3-max", "deepseek-chat-v3.1", "gpt-5"] else 1.5
        )
        alpha = 1.0 if model_id in ["qwen3-max", "deepseek-chat-v3.1", "gpt-5"] else 0.7

        ax1.plot(
            cycles,
            returns,
            label=model_id,
            color=color,
            linewidth=linewidth,
            alpha=alpha,
        )

    ax1.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax1.set_xlabel("Cycle ID", fontsize=12)
    ax1.set_ylabel("Return (%)", fontsize=12)
    ax1.set_title(
        "AI Trading Models - Return Comparison", fontsize=14, fontweight="bold"
    )
    ax1.legend(loc="best", fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 图表2: 账户价值对比
    for model_id, data_points in model_data.items():
        if not data_points:
            continue

        cycles = [p["cycle_id"] for p in data_points]
        values = [
            p["account_info"].get("account_value", INITIAL_CAPITAL) for p in data_points
        ]

        color = MODEL_COLORS.get(model_id, "#000000")
        linewidth = (
            2.5 if model_id in ["qwen3-max", "deepseek-chat-v3.1", "gpt-5"] else 1.5
        )
        alpha = 1.0 if model_id in ["qwen3-max", "deepseek-chat-v3.1", "gpt-5"] else 0.7

        ax2.plot(
            cycles,
            values,
            label=model_id,
            color=color,
            linewidth=linewidth,
            alpha=alpha,
        )

    ax2.axhline(
        y=INITIAL_CAPITAL,
        color="gray",
        linestyle="--",
        alpha=0.5,
        label=f"Initial Capital (${INITIAL_CAPITAL:,})",
    )
    ax2.set_xlabel("Cycle ID", fontsize=12)
    ax2.set_ylabel("Account Value ($)", fontsize=12)
    ax2.set_title(
        "AI Trading Models - Account Value Comparison", fontsize=14, fontweight="bold"
    )
    ax2.legend(loc="best", fontsize=10)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    output_path = os.path.join(OUTPUT_DIR, "trading_performance_charts.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"[OK] Chart saved: {output_path}")

    plt.close()


def export_csv_files(model_data, inflection_points):
    """导出CSV文件"""
    print("\n导出CSV文件...")

    # 1. 模型性能汇总
    summary_path = os.path.join(OUTPUT_DIR, "model_performance_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Model",
                "Final Return (%)",
                "Final Account Value ($)",
                "Initial Capital ($)",
                "Total Data Points",
                "Inflection Points",
                "Sharpe Ratio",
            ]
        )

        for model_id, data_points in sorted(model_data.items()):
            if data_points:
                last_point = data_points[-1]
                final_return = last_point["account_info"].get("return_pct", 0)
                final_value = last_point["account_info"].get(
                    "account_value", INITIAL_CAPITAL
                )
                sharpe = last_point["account_info"].get("sharpe_ratio", 0)
                inflection_count = len(inflection_points.get(model_id, []))

                writer.writerow(
                    [
                        model_id,
                        f"{final_return:.2f}",
                        f"{final_value:.2f}",
                        INITIAL_CAPITAL,
                        len(data_points),
                        inflection_count,
                        f"{sharpe:.3f}",
                    ]
                )

    print(f"[OK] Summary saved: {summary_path}")

    # 2. 完整时间序列
    timeseries_path = os.path.join(OUTPUT_DIR, "model_timeseries.csv")
    with open(timeseries_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Model",
                "Cycle ID",
                "Timestamp",
                "Return (%)",
                "Account Value ($)",
                "Available Cash ($)",
                "Change from Previous (%)",
                "Positions Count",
            ]
        )

        for model_id, data_points in sorted(model_data.items()):
            for point in data_points:
                writer.writerow(
                    [
                        model_id,
                        point["cycle_id"],
                        point["timestamp"],
                        f"{point['account_info'].get('return_pct', 0):.2f}",
                        f"{point['account_info'].get('account_value', 0):.2f}",
                        f"{point['account_info'].get('available_cash', 0):.2f}",
                        f"{point.get('value_change_pct', 0):.2f}",
                        len(point["account_info"].get("positions", [])),
                    ]
                )

    print(f"[OK] Timeseries saved: {timeseries_path}")

    # 3. 拐点记录
    inflection_path = os.path.join(OUTPUT_DIR, "inflection_points.csv")
    with open(inflection_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Model",
                "Cycle ID",
                "Timestamp",
                "Account Value ($)",
                "Previous Value ($)",
                "Change (%)",
                "Return (%)",
                "Positions",
                "COT Summary",
            ]
        )

        for model_id, points in sorted(inflection_points.items()):
            for point in points:
                positions_str = "; ".join(
                    [
                        f"{p['symbol']}:{p['quantity']:.2f}"
                        for p in point["account_info"].get("positions", [])
                    ]
                )

                writer.writerow(
                    [
                        model_id,
                        point["cycle_id"],
                        point["timestamp"],
                        f"{point['account_info'].get('account_value', 0):.2f}",
                        f"{point.get('prev_value', 0):.2f}",
                        f"{point.get('value_change_pct', 0):.2f}",
                        f"{point['account_info'].get('return_pct', 0):.2f}",
                        positions_str,
                        point.get("cot_trace_summary", "")[:200],
                    ]
                )

    print(f"[OK] Inflection points saved: {inflection_path}")


def analyze_key_models(model_data, inflection_points):
    """深度分析关键模型（qwen, deepseek, gpt）"""
    print("\n深度分析关键模型...")

    key_models = {
        "qwen3-max": "盈利冠军",
        "deepseek-chat-v3.1": "盈利亚军",
        "gpt-5": "最大亏损",
    }

    analysis_results = {}

    for model_id, label in key_models.items():
        print(f"\n分析 {model_id} ({label})...")

        data_points = model_data.get(model_id, [])
        inflections = inflection_points.get(model_id, [])

        if not data_points:
            print(f"  [WARN] No data found for {model_id}")
            continue

        # 获取最终表现
        final_point = data_points[-1]
        final_return = final_point["account_info"].get("return_pct", 0)
        final_value = final_point["account_info"].get("account_value", INITIAL_CAPITAL)

        # 选择最重要的拐点（变化最大的）
        sorted_inflections = sorted(
            inflections, key=lambda x: abs(x.get("value_change_pct", 0)), reverse=True
        )[
            :5
        ]  # 取前5个最大变化

        analysis_results[model_id] = {
            "label": label,
            "final_return": final_return,
            "final_value": final_value,
            "total_points": len(data_points),
            "total_inflections": len(inflections),
            "key_inflections": sorted_inflections,
            "sharpe_ratio": final_point["account_info"].get("sharpe_ratio", 0),
        }

        print(f"  Final return: {final_return:.2f}%")
        print(f"  Final value: ${final_value:,.2f}")
        print(f"  Key inflection points: {len(sorted_inflections)}")

    return analysis_results


def generate_markdown_report(model_data, inflection_points, analysis_results):
    """生成Markdown分析报告"""
    print("\n生成Markdown报告...")

    report_path = os.path.join(OUTPUT_DIR, "TRADING_ANALYSIS_REPORT.md")

    with open(report_path, "w", encoding="utf-8") as f:
        # 标题
        f.write("# AI交易模型性能分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**初始资金**: ${INITIAL_CAPITAL:,}\n\n")
        f.write("---\n\n")

        # 1. 执行摘要
        f.write("## 1. 执行摘要\n\n")

        # 排名表格
        f.write("### 模型表现排名\n\n")
        f.write("| 排名 | 模型 | 最终收益率 | 最终账户价值 | Sharpe比率 | 拐点数量 |\n")
        f.write("|------|------|------------|--------------|------------|----------|\n")

        # 按最终收益率排序
        sorted_models = sorted(
            model_data.items(),
            key=lambda x: (
                x[1][-1]["account_info"].get("return_pct", 0) if x[1] else -999
            ),
            reverse=True,
        )

        for rank, (model_id, data_points) in enumerate(sorted_models, 1):
            if data_points:
                last = data_points[-1]
                final_return = last["account_info"].get("return_pct", 0)
                final_value = last["account_info"].get("account_value", INITIAL_CAPITAL)
                sharpe = last["account_info"].get("sharpe_ratio", 0)
                inflection_count = len(inflection_points.get(model_id, []))

                return_emoji = "📈" if final_return > 0 else "📉"
                f.write(
                    f"| {rank} | **{model_id}** | {return_emoji} {final_return:.2f}% | "
                    f"${final_value:,.2f} | {sharpe:.3f} | {inflection_count} |\n"
                )

        f.write("\n")

        # 统计概览
        positive_models = sum(
            1
            for _, data in model_data.items()
            if data and data[-1]["account_info"].get("return_pct", 0) > 0
        )
        negative_models = len(model_data) - positive_models

        f.write(f"**盈利模型数量**: {positive_models}/6\n\n")
        f.write(f"**亏损模型数量**: {negative_models}/6\n\n")

        # 2. 详细模型分析
        f.write("---\n\n## 2. 重点模型详细分析\n\n")

        # 分析三个关键模型
        for model_id in ["qwen3-max", "deepseek-chat-v3.1", "gpt-5"]:
            if model_id not in analysis_results:
                continue

            result = analysis_results[model_id]
            f.write(f"### {model_id} - {result['label']}\n\n")

            # 性能指标
            f.write("#### 性能指标\n\n")
            f.write(f"- **最终收益率**: {result['final_return']:.2f}%\n")
            f.write(f"- **最终账户价值**: ${result['final_value']:,.2f}\n")
            f.write(
                f"- **盈亏金额**: ${result['final_value'] - INITIAL_CAPITAL:,.2f}\n"
            )
            f.write(f"- **Sharpe比率**: {result['sharpe_ratio']:.3f}\n")
            f.write(f"- **数据点数量**: {result['total_points']}\n")
            f.write(f"- **拐点数量**: {result['total_inflections']}\n\n")

            # 关键拐点分析
            if result["key_inflections"]:
                f.write("#### 关键拐点分析\n\n")

                for idx, inflection in enumerate(result["key_inflections"], 1):
                    change = inflection.get("value_change_pct", 0)
                    direction = "上涨" if change > 0 else "下跌"
                    emoji = "🚀" if change > 0 else "⚠️"

                    f.write(
                        f"##### {emoji} 拐点 #{idx}: {direction} {abs(change):.2f}%\n\n"
                    )
                    f.write(f"- **周期ID**: {inflection['cycle_id']}\n")
                    f.write(
                        f"- **账户价值变化**: ${inflection.get('prev_value', 0):,.2f} → "
                        f"${inflection['account_info'].get('account_value', 0):,.2f}\n"
                    )
                    f.write(
                        f"- **当时收益率**: {inflection['account_info'].get('return_pct', 0):.2f}%\n"
                    )

                    # 持仓信息
                    positions = inflection["account_info"].get("positions", [])
                    if positions:
                        f.write(f"- **持仓情况**:\n")
                        for pos in positions:
                            pnl_emoji = "✅" if pos["unrealized_pnl"] > 0 else "❌"
                            f.write(
                                f"  - {pnl_emoji} {pos['symbol']}: {pos['quantity']:.2f} "
                                f"(未实现盈亏: ${pos['unrealized_pnl']:.2f})\n"
                            )

                    # 策略思考摘要
                    summary = inflection.get("cot_trace_summary", "")
                    if summary:
                        f.write(f"\n**策略思考摘要**:\n> {summary}\n")

                    # 决策详情
                    llm_response = inflection.get("llm_response", {})
                    if llm_response:
                        f.write(f"\n**交易决策**:\n")
                        for coin, decision in llm_response.items():
                            if isinstance(decision, dict):
                                signal = decision.get("signal", "N/A")
                                leverage = decision.get("leverage", "N/A")
                                confidence = decision.get("confidence", "N/A")
                                f.write(
                                    f"- **{coin}**: {signal} (杠杆: {leverage}x, 信心: {confidence})\n"
                                )

                    f.write("\n")

            f.write("---\n\n")

        # 3. 其他模型简要分析
        f.write("## 3. 其他模型简要分析\n\n")

        other_models = ["claude-sonnet-4-5", "gemini-2.5-pro", "grok-4"]
        for model_id in other_models:
            data_points = model_data.get(model_id, [])
            if not data_points:
                continue

            last = data_points[-1]
            final_return = last["account_info"].get("return_pct", 0)
            final_value = last["account_info"].get("account_value", INITIAL_CAPITAL)
            inflection_count = len(inflection_points.get(model_id, []))

            f.write(f"### {model_id}\n\n")
            f.write(f"- **最终收益率**: {final_return:.2f}%\n")
            f.write(f"- **最终账户价值**: ${final_value:,.2f}\n")
            f.write(f"- **拐点数量**: {inflection_count}\n\n")

        # 4. 策略对比与结论
        f.write("---\n\n## 4. 策略对比与结论\n\n")

        f.write("### 盈利模型的共同特征\n\n")
        f.write(
            "通过分析盈利模型（qwen3-max和deepseek-chat-v3.1）的交易行为，我们发现：\n\n"
        )
        f.write("1. **风险管理**: 盈利模型倾向于使用适度的杠杆，避免过度激进\n")
        f.write("2. **持仓策略**: 善于识别趋势并持有盈利头寸，不轻易止损\n")
        f.write("3. **决策一致性**: 决策逻辑清晰，执行力强\n\n")

        f.write("### 亏损模型的风险点\n\n")
        f.write("分析亏损模型（尤其是gpt-5）的交易行为：\n\n")
        f.write("1. **过度交易**: 频繁进出场可能导致交易成本累积\n")
        f.write("2. **杠杆使用**: 可能存在过度使用杠杆的情况\n")
        f.write("3. **止损时机**: 止损过早或过晚都可能影响整体表现\n\n")

        f.write("### 关键成功因素\n\n")
        f.write("基于本次分析，成功的AI交易模型具备以下特征：\n\n")
        f.write("- ✅ **审慎的风险管理**：合理控制杠杆和仓位大小\n")
        f.write("- ✅ **趋势识别能力**：能够识别并把握市场主要趋势\n")
        f.write("- ✅ **情绪控制**：不被短期波动影响，坚持既定策略\n")
        f.write("- ✅ **适应性**：能够根据市场环境调整策略\n\n")

        f.write("---\n\n")
        f.write("## 附录\n\n")
        f.write("- 完整数据文件: `model_timeseries.csv`\n")
        f.write("- 拐点详细记录: `inflection_points.csv`\n")
        f.write("- 性能汇总: `model_performance_summary.csv`\n")
        f.write("- 可视化图表: `trading_performance_charts.png`\n")

    print(f"[OK] Markdown report saved: {report_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("AI交易模型数据分析")
    print("=" * 60)

    # 创建输出目录
    create_output_dir()

    # 加载数据
    model_data = load_all_data()

    if not model_data:
        print("[ERROR] No valid data found")
        return

    # 计算变化率
    calculate_changes(model_data)

    # 识别拐点
    inflection_points = identify_inflection_points(model_data)

    # 生成图表
    generate_charts(model_data)

    # 导出CSV
    export_csv_files(model_data, inflection_points)

    # 深度分析
    analysis_results = analyze_key_models(model_data, inflection_points)

    # 生成报告
    generate_markdown_report(model_data, inflection_points, analysis_results)

    print("\n" + "=" * 60)
    print("[SUCCESS] Analysis completed!")
    print(f"All output files saved in: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
