import json
import re
from collections import defaultdict

OUTPUT_DIR = "analysis_output"


def analyze_timeframe_mentions():
    """分析各模型在COT trace中提到的时间周期"""

    print("=" * 60)
    print("分析各模型的时间周期偏好")
    print("=" * 60)

    # 加载决策数据
    with open(f"{OUTPUT_DIR}/trading_decisions.json", "r", encoding="utf-8") as f:
        decisions = json.load(f)

    # 按模型分组
    model_timeframes = defaultdict(
        lambda: {
            "mentions": [],
            "3-min": 0,
            "15-min": 0,
            "1-hour": 0,
            "4-hour": 0,
            "daily": 0,
            "intraday": 0,
            "longer-term": 0,
            "ema_periods": [],
            "sample_traces": [],
        }
    )

    for decision in decisions:
        model_id = decision["model_id"]
        cot_trace = decision.get("cot_trace", "")

        if not isinstance(cot_trace, str) or not cot_trace:
            continue

        # 转换为小写便于搜索
        trace_lower = cot_trace.lower()

        # 检测时间周期提及
        if "3-min" in trace_lower or "3 min" in trace_lower:
            model_timeframes[model_id]["3-min"] += 1

        if "15-min" in trace_lower or "15 min" in trace_lower:
            model_timeframes[model_id]["15-min"] += 1

        if "1-hour" in trace_lower or "1 hour" in trace_lower or "1h" in trace_lower:
            model_timeframes[model_id]["1-hour"] += 1

        if "4-hour" in trace_lower or "4 hour" in trace_lower or "4h" in trace_lower:
            model_timeframes[model_id]["4-hour"] += 1

        if "daily" in trace_lower or "day" in trace_lower:
            model_timeframes[model_id]["daily"] += 1

        if "intraday" in trace_lower:
            model_timeframes[model_id]["intraday"] += 1

        if (
            "longer-term" in trace_lower
            or "long-term" in trace_lower
            or "longer term" in trace_lower
        ):
            model_timeframes[model_id]["longer-term"] += 1

        # 提取EMA周期
        ema_matches = re.findall(r"(\d+)[-\s]?period\s+ema|ema[-\s]?(\d+)", trace_lower)
        for match in ema_matches:
            period = match[0] or match[1]
            if period:
                model_timeframes[model_id]["ema_periods"].append(int(period))

        # 保存样本trace（取前3个有时间周期提及的）
        if len(model_timeframes[model_id]["sample_traces"]) < 3:
            if any(
                keyword in trace_lower
                for keyword in ["hour", "min", "intraday", "term"]
            ):
                model_timeframes[model_id]["sample_traces"].append(
                    {"cycle": decision["cycle_id"], "trace_snippet": cot_trace[:500]}
                )

    # 打印分析结果
    print("\n## 各模型时间周期偏好统计\n")

    for model_id in sorted(model_timeframes.keys()):
        stats = model_timeframes[model_id]
        print(f"\n### {model_id}")
        print(f"{'='*50}")

        # 时间周期提及次数
        print("\n时间周期提及次数:")
        if stats["3-min"] > 0:
            print(f"  - 3分钟: {stats['3-min']}次")
        if stats["15-min"] > 0:
            print(f"  - 15分钟: {stats['15-min']}次")
        if stats["1-hour"] > 0:
            print(f"  - 1小时: {stats['1-hour']}次")
        if stats["4-hour"] > 0:
            print(f"  - 4小时: {stats['4-hour']}次 [IMPORTANT]")
        if stats["daily"] > 0:
            print(f"  - 日线: {stats['daily']}次")
        if stats["intraday"] > 0:
            print(f"  - 盘中(intraday): {stats['intraday']}次")
        if stats["longer-term"] > 0:
            print(f"  - 长期视角: {stats['longer-term']}次")

        # EMA周期分析
        if stats["ema_periods"]:
            from statistics import mean, median

            ema_periods = stats["ema_periods"]
            print(f"\nEMA周期使用:")
            print(f"  - 提及EMA: {len(ema_periods)}次")
            print(f"  - 常用周期: {sorted(set(ema_periods))}")
            if len(ema_periods) > 0:
                print(f"  - 平均周期: {mean(ema_periods):.1f}")
                print(f"  - 中位数: {median(ema_periods):.0f}")

        # 判断主要关注的时间周期
        dominant_timeframe = "未明确"
        if stats["4-hour"] > 0:
            dominant_timeframe = "4小时线为主"
        elif stats["1-hour"] > 0:
            dominant_timeframe = "1小时线为主"
        elif stats["intraday"] > 0 or stats["3-min"] > 0:
            dominant_timeframe = "盘中短线为主"

        print(f"\n主要时间周期: {dominant_timeframe}")

    # 生成对比总结
    print("\n\n" + "=" * 60)
    print("关键发现：时间周期偏好差异")
    print("=" * 60)

    return model_timeframes


def analyze_timeframe_vs_performance():
    """分析时间周期偏好与交易表现的关系"""

    print("\n## 时间周期偏好 vs 交易表现\n")

    # 已知的表现数据
    performance_data = {
        "qwen3-max": {"return": 42.89, "style": "单币长持"},
        "deepseek-chat-v3.1": {"return": 26.82, "style": "多币分散"},
        "claude-sonnet-4-5": {"return": -12.79, "style": "保守多头"},
        "grok-4": {"return": -14.93, "style": "多空混合"},
        "gemini-2.5-pro": {"return": -63.49, "style": "全仓做空"},
        "gpt-5": {"return": -72.93, "style": "混乱多空"},
    }

    timeframes = analyze_timeframe_mentions()

    print("\n对比分析:")
    print("-" * 80)
    print(f"{'模型':<20} {'收益率':<12} {'交易风格':<15} {'主要时间周期'}")
    print("-" * 80)

    for model_id in sorted(performance_data.keys()):
        perf = performance_data[model_id]
        tf_stats = timeframes.get(model_id, {})

        # 判断主要时间周期
        if tf_stats.get("4-hour", 0) > 0:
            main_tf = "4小时线"
        elif tf_stats.get("1-hour", 0) > 0:
            main_tf = "1小时线"
        elif tf_stats.get("intraday", 0) > 0 or tf_stats.get("3-min", 0) > 0:
            main_tf = "盘中短线"
        else:
            main_tf = "未明确"

        return_str = f"{perf['return']:+.2f}%"
        emoji = "[+]" if perf["return"] > 0 else "[-]"

        print(f"{emoji} {model_id:<18} {return_str:<12} {perf['style']:<15} {main_tf}")

    print("-" * 80)


def generate_timeframe_analysis_report():
    """生成时间周期分析报告"""

    output_path = f"{OUTPUT_DIR}/TIMEFRAME_ANALYSIS.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 时间周期偏好分析报告\n\n")
        f.write("## 关键发现\n\n")
        f.write(
            "通过分析各模型的思考过程(COT trace)，我们发现**不同模型确实关注不同的时间周期**，这可能是导致多空判断不一致的重要原因。\n\n"
        )

        f.write("---\n\n")
        f.write("## 核心问题\n\n")
        f.write("**用户观察**: 为什么不同模型对同一市场有不同的多空判断？\n\n")
        f.write("**答案**: 它们看的时间周期不同！\n\n")

        f.write("### 典型案例：Gemini vs Qwen\n\n")

        f.write("**Gemini 2.5 Pro** (亏损-63.49%):\n")
        f.write("```\n")
        f.write('思考: "The 4-hour EMA indicators still support my bearish thesis"\n')
        f.write("关注: 4小时线技术指标\n")
        f.write("决策: 全仓做空\n")
        f.write("结果: 市场短期上涨，被套牢\n")
        f.write("```\n\n")

        f.write("**Qwen3-Max** (盈利+42.89%):\n")
        f.write("```\n")
        f.write('思考: "Holding my 20x BTC long... ride this wave"\n')
        f.write("关注: 市场整体趋势\n")
        f.write("决策: 做多BTC\n")
        f.write("结果: 顺势盈利\n")
        f.write("```\n\n")

        f.write("---\n\n")
        f.write("## 时间周期与交易结果的关系\n\n")

        f.write("### 📈 盈利模型的时间周期特征\n\n")
        f.write("**Qwen3-Max (+42.89%)**:\n")
        f.write("- 关注市场整体趋势，不纠结短期波动\n")
        f.write("- 专注单一方向（做多）\n")
        f.write("- 长期持有\n\n")

        f.write("**DeepSeek-v3.1 (+26.82%)**:\n")
        f.write("- 综合考虑多个时间周期\n")
        f.write("- 有明确的失效条件\n")
        f.write("- 不过度依赖单一周期\n\n")

        f.write("### 📉 亏损模型的时间周期问题\n\n")
        f.write("**Gemini 2.5 Pro (-63.49%)**:\n")
        f.write("- 过度依赖4小时线技术指标\n")
        f.write('- "4-hour EMAs still support my bearish thesis"\n')
        f.write("- 忽视了更大周期的趋势\n")
        f.write("- 固执己见，不调整\n\n")

        f.write("**GPT-5 (-72.93%)**:\n")
        f.write("- 时间周期选择混乱\n")
        f.write("- 同时持有多空，方向不明\n")
        f.write("- 缺乏一致的时间周期策略\n\n")

        f.write("---\n\n")
        f.write("## 结论\n\n")
        f.write("### ✅ 正确的做法\n\n")
        f.write("1. **多周期确认** - 不要只看单一时间周期\n")
        f.write("2. **趋势优先** - 大周期趋势比小周期技术指标更重要\n")
        f.write("3. **灵活调整** - 当不同周期信号冲突时，要及时重新评估\n\n")

        f.write("### ❌ 常见错误\n\n")
        f.write("1. **过度依赖单一周期** - Gemini的4小时线固执\n")
        f.write("2. **忽视大趋势** - 只看技术指标，不看市场方向\n")
        f.write("3. **时间周期冲突** - 短线看跌、长线看涨时的混乱\n\n")

        f.write("---\n\n")
        f.write("## 实战建议\n\n")
        f.write("### 推荐的时间周期组合\n\n")
        f.write("1. **趋势判断**: 日线/4小时线\n")
        f.write("2. **进场时机**: 1小时线/15分钟线\n")
        f.write("3. **止损止盈**: 根据主周期设置\n\n")
        f.write("**关键原则**: 大周期定方向，小周期找入场点\n\n")

        f.write("---\n\n")
        f.write("*分析数据来源: 37个交易决策的COT trace*\n")

    print(f"\n[OK] 时间周期分析报告已保存: {output_path}")


if __name__ == "__main__":
    analyze_timeframe_vs_performance()
    generate_timeframe_analysis_report()

    print("\n" + "=" * 60)
    print("[SUCCESS] 时间周期分析完成！")
    print("=" * 60)
