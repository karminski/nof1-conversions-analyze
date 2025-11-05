import json
import csv
from datetime import datetime
from collections import defaultdict

OUTPUT_DIR = "analysis_output"


def load_trading_decisions():
    """加载交易决策数据"""
    with open(f"{OUTPUT_DIR}/trading_decisions.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_position_changes_csv():
    """加载CSV数据"""
    changes = []
    with open(f"{OUTPUT_DIR}/position_changes.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            changes.append(row)
    return changes


def extract_key_decisions(model_id, decisions):
    """提取指定模型的关键决策"""
    model_decisions = [d for d in decisions if d["model_id"] == model_id]

    # 按时间排序
    model_decisions.sort(key=lambda x: x["timestamp"])

    return model_decisions


def format_decision_timeline(decisions):
    """格式化决策时间线"""
    lines = []

    for idx, decision in enumerate(decisions, 1):
        cycle = decision["cycle_id"]
        change_type = decision["change_type"]
        coin = decision["coin"]
        prev_qty = decision["prev_quantity"]
        new_qty = decision["new_quantity"]
        leverage = decision.get("leverage", "N/A")
        account_value = decision["account_value"]
        return_pct = decision["return_pct"]

        # 操作类型中文
        action_map = {
            "open_long": f"开仓做多 {coin}",
            "open_short": f"开仓做空 {coin}",
            "close_long": f"平仓(多头) {coin}",
            "close_short": f"平仓(空头) {coin}",
            "add_position": f"加仓 {coin}",
            "reduce_position": f"减仓 {coin}",
            "flip_position": f"翻转 {coin}",
        }
        action_title = action_map.get(change_type, change_type)

        lines.append(f"\n###### {idx}. Cycle {cycle}: {action_title}\n")

        if "open" in change_type:
            direction = "做多" if "long" in change_type else "做空"
            lines.append(
                f"- **操作**: {direction} {abs(new_qty):.2f} @ {leverage}x杠杆\n"
            )
        elif "close" in change_type:
            lines.append(f"- **操作**: 平仓 {abs(prev_qty):.2f}\n")
        else:
            lines.append(f"- **操作**: {abs(prev_qty):.2f} → {abs(new_qty):.2f}\n")

        lines.append(
            f"- **账户状态**: ${account_value:,.2f} (收益率: {return_pct:.2f}%)\n"
        )

        # 决策摘要
        summary = decision.get("cot_trace_summary", "")
        if summary:
            lines.append(f"\n**策略思考**:\n> {summary}\n")

        # 从完整trace中提取关键信息
        cot_trace = decision.get("cot_trace", "")
        key_insights = extract_key_insights(cot_trace)
        if key_insights:
            lines.append(f"\n**决策要点**:\n")
            for insight in key_insights:
                lines.append(f"- {insight}\n")

    return "".join(lines)


def extract_key_insights(cot_trace):
    """从思考过程中提取关键洞察"""
    if not cot_trace or not isinstance(cot_trace, str):
        return []

    insights = []

    # 检测技术指标提及
    if "EMA" in cot_trace.upper() or "ema" in cot_trace:
        insights.append("🔍 使用EMA技术指标分析")

    if "MACD" in cot_trace.upper():
        insights.append("📊 参考MACD动量指标")

    if "RSI" in cot_trace.upper():
        insights.append("📈 考虑RSI超买超卖")

    # 检测风险管理
    if "stop loss" in cot_trace.lower() or "stop-loss" in cot_trace.lower():
        insights.append("🛡️ 设置止损保护")

    if "risk" in cot_trace.lower():
        insights.append("⚠️ 关注风险管理")

    # 检测市场判断
    if "bullish" in cot_trace.lower():
        insights.append("📈 判断市场看涨")
    elif "bearish" in cot_trace.lower():
        insights.append("📉 判断市场看跌")

    # 检测持仓策略
    if "hold" in cot_trace.lower() and "ing" in cot_trace.lower():
        insights.append("💎 坚持持有策略")

    if "overtrading" in cot_trace.lower():
        insights.append("🚫 避免过度交易")

    return insights[:5]  # 最多返回5个关键点


def analyze_decision_pattern(decisions):
    """分析决策模式"""
    if not decisions:
        return ""

    lines = []
    lines.append("\n#### 决策模式分析\n\n")

    # 统计
    total_trades = len(decisions)
    open_trades = len([d for d in decisions if "open" in d["change_type"]])
    close_trades = len([d for d in decisions if "close" in d["change_type"]])
    long_trades = len([d for d in decisions if "long" in d["change_type"]])
    short_trades = len([d for d in decisions if "short" in d["change_type"]])

    lines.append(f"**交易统计**:\n")
    lines.append(f"- 总交易次数: {total_trades}\n")
    lines.append(f"- 开仓次数: {open_trades}\n")
    lines.append(f"- 平仓次数: {close_trades}\n")
    lines.append(f"- 做多次数: {long_trades}\n")
    lines.append(f"- 做空次数: {short_trades}\n\n")

    # 交易风格
    lines.append(f"**交易风格**:\n")
    if total_trades <= 2:
        lines.append(f"- 📉 **极低频交易**: 高度专注，长期持有\n")
    elif total_trades <= 5:
        lines.append(f"- 📊 **低频交易**: 选择性进场，注重质量\n")
    elif total_trades <= 10:
        lines.append(f"- 📈 **中频交易**: 适度活跃，平衡进出\n")
    else:
        lines.append(f"- 🔄 **高频交易**: 频繁调整，积极操作\n")

    if long_trades > 0 and short_trades > 0:
        lines.append(f"- ⚖️ **多空双向**: 同时使用多头和空头策略\n")
    elif long_trades > 0:
        lines.append(f"- 📈 **纯多头**: 仅做多，顺势交易\n")
    elif short_trades > 0:
        lines.append(f"- 📉 **纯空头**: 仅做空，逆势或对冲\n")

    # 持仓时长
    if len(decisions) >= 2:
        first_trade = decisions[0]
        last_trade = decisions[-1]
        duration_cycles = last_trade["cycle_id"] - first_trade["cycle_id"]
        lines.append(f"- ⏱️ **活跃周期**: {duration_cycles} cycles\n")

    return "".join(lines)


def generate_enhanced_report():
    """生成增强版报告"""
    print("生成增强版交易分析报告...")

    # 加载数据
    decisions = load_trading_decisions()

    # 重点模型
    key_models = {
        "qwen3-max": "盈利冠军 +42.89%",
        "deepseek-chat-v3.1": "盈利亚军 +26.82%",
        "gpt-5": "最大亏损 -72.93%",
        "gemini-2.5-pro": "第二大亏损 -63.49%",
    }

    report_path = f"{OUTPUT_DIR}/TRADING_ANALYSIS_REPORT.md"

    # 读取现有报告
    with open(report_path, "r", encoding="utf-8") as f:
        existing_report = f.read()

    # 为每个重点模型生成详细分析
    enhanced_sections = {}

    for model_id, label in key_models.items():
        print(f"  分析 {model_id}...")

        model_decisions = extract_key_decisions(model_id, decisions)

        section = []
        section.append(f"\n#### 交易决策时间线\n")

        if model_decisions:
            timeline = format_decision_timeline(model_decisions)
            section.append(timeline)

            pattern = analyze_decision_pattern(model_decisions)
            section.append(pattern)
        else:
            section.append(f"\n*在数据采集期间未检测到明显的持仓变化*\n")

        enhanced_sections[model_id] = "".join(section)

    # 插入增强内容到报告中
    enhanced_report = existing_report

    # 为每个模型添加新章节
    for model_id, content in enhanced_sections.items():
        # 找到该模型的章节，在"关键拐点分析"之后插入
        marker = f"### {model_id} -"
        if marker in enhanced_report:
            # 找到下一个 "---" 的位置
            start_pos = enhanced_report.find(marker)
            end_marker = "\n---\n"
            end_pos = enhanced_report.find(end_marker, start_pos)

            if end_pos != -1:
                # 在 "---" 之前插入新内容
                enhanced_report = (
                    enhanced_report[:end_pos] + content + enhanced_report[end_pos:]
                )

    # 保存增强报告
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(enhanced_report)

    print(f"[OK] 增强报告已保存: {report_path}")


def generate_decision_patterns_doc():
    """生成决策模式专题文档"""
    print("\n生成决策模式专题分析...")

    decisions = load_trading_decisions()

    output_path = f"{OUTPUT_DIR}/DECISION_PATTERNS.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# AI交易模型决策模式深度分析\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        f.write("## 概述\n\n")
        f.write(
            f"本文档深入分析了6个AI交易模型的所有交易决策，共检测到**{len(decisions)}个持仓变化**。\n\n"
        )

        # 按模型分组
        model_groups = defaultdict(list)
        for d in decisions:
            model_groups[d["model_id"]].append(d)

        # 生成各模型详细分析
        for model_id in sorted(model_groups.keys()):
            model_decisions = model_groups[model_id]

            f.write(f"---\n\n## {model_id}\n\n")
            f.write(f"**总交易次数**: {len(model_decisions)}\n\n")

            # 决策时间线
            f.write("### 完整交易记录\n")
            timeline = format_decision_timeline(model_decisions)
            f.write(timeline)

            # 模式分析
            pattern = analyze_decision_pattern(model_decisions)
            f.write(pattern)

    print(f"[OK] 决策模式文档已保存: {output_path}")


def main():
    print("=" * 60)
    print("生成增强分析报告")
    print("=" * 60)

    # 生成增强报告
    generate_enhanced_report()

    # 生成决策模式文档
    generate_decision_patterns_doc()

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有报告生成完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
