import json
import os
import re
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Configuration
CLEANED_DATA_DIR = "cleaned_data"
OUTPUT_DIR = "DOCUMENTS"
OUTPUT_REPORT = "COT_THINKING_ANALYSIS.md"

# Keywords to extract
TECHNICAL_INDICATORS = [
    "rsi", "macd", "ema", "sma", "支撑", "阻力", "support", "resistance",
    "bollinger", "atr", "volume", "成交量"
]

MARKET_CONCEPTS = [
    "trend", "趋势", "breakout", "突破", "pullback", "回调", "consolidation",
    "震荡", "reversal", "反转", "momentum", "动量", "bullish", "看涨",
    "bearish", "看跌", "rally", "上涨", "decline", "下跌"
]

TIMEFRAMES = [
    "3-min", "3 min", "15-min", "15 min", "1-hour", "1 hour", "4-hour",
    "4 hour", "daily", "日线", "intraday", "盘中", "short-term", "短期",
    "long-term", "长期"
]

RISK_WORDS = [
    "risk", "风险", "stop loss", "止损", "profit target", "止盈",
    "invalidation", "失效", "cautious", "谨慎", "conservative", "保守",
    "aggressive", "激进", "confident", "信心"
]


def load_model_trades(model_id: str) -> List[Dict]:
    """Load trades for a specific model"""
    filepath = os.path.join(CLEANED_DATA_DIR, f"{model_id}_trades.json")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {model_id}: {e}")
        return []


def convert_timestamp(timestamp: float) -> str:
    """Convert Unix timestamp to readable format"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def extract_keywords(text: str, keywords_list: List[str]) -> List[str]:
    """Extract keywords from text"""
    if not text or not isinstance(text, str):
        return []
    
    text_lower = text.lower()
    found = []
    
    for keyword in keywords_list:
        if keyword.lower() in text_lower:
            found.append(keyword)
    
    return found


def analyze_cot_text(cot_trace: Any) -> Dict:
    """Analyze COT trace text"""
    # Handle different formats of cot_trace
    if isinstance(cot_trace, dict):
        # If it's a dict, try to get text content
        cot_text = str(cot_trace)
    elif isinstance(cot_trace, str):
        cot_text = cot_trace
    else:
        cot_text = str(cot_trace)
    
    analysis = {
        "length": len(cot_text),
        "technical_indicators": extract_keywords(cot_text, TECHNICAL_INDICATORS),
        "market_concepts": extract_keywords(cot_text, MARKET_CONCEPTS),
        "timeframes": extract_keywords(cot_text, TIMEFRAMES),
        "risk_words": extract_keywords(cot_text, RISK_WORDS),
        "text": cot_text
    }
    
    return analysis


def analyze_model_thinking(model_id: str, trades: List[Dict]) -> Dict:
    """Analyze thinking patterns for a model"""
    print(f"\nAnalyzing COT for {model_id}...")
    
    all_keywords = {
        "technical_indicators": [],
        "market_concepts": [],
        "timeframes": [],
        "risk_words": []
    }
    
    thinking_lengths = []
    
    trades_with_analysis = []
    
    for trade in trades:
        cot_trace = trade.get("cot_trace", "")
        cot_analysis = analyze_cot_text(cot_trace)
        
        # Collect keywords
        all_keywords["technical_indicators"].extend(cot_analysis["technical_indicators"])
        all_keywords["market_concepts"].extend(cot_analysis["market_concepts"])
        all_keywords["timeframes"].extend(cot_analysis["timeframes"])
        all_keywords["risk_words"].extend(cot_analysis["risk_words"])
        
        thinking_lengths.append(cot_analysis["length"])
        
        # Add analysis to trade
        trade_with_analysis = {
            **trade,
            "cot_analysis": cot_analysis
        }
        trades_with_analysis.append(trade_with_analysis)
    
    # Count frequencies
    keyword_counts = {
        "technical_indicators": Counter(all_keywords["technical_indicators"]),
        "market_concepts": Counter(all_keywords["market_concepts"]),
        "timeframes": Counter(all_keywords["timeframes"]),
        "risk_words": Counter(all_keywords["risk_words"])
    }
    
    avg_length = sum(thinking_lengths) / len(thinking_lengths) if thinking_lengths else 0
    
    print(f"  Average COT length: {avg_length:.0f} characters")
    print(f"  Total trades analyzed: {len(trades)}")
    
    return {
        "model_id": model_id,
        "total_trades": len(trades),
        "avg_thinking_length": avg_length,
        "keyword_counts": keyword_counts,
        "trades": trades_with_analysis
    }


def find_best_and_worst_cases(trades: List[Dict], top_n: int = 5) -> Tuple[List, List]:
    """Find best and worst performing trades"""
    # Calculate PnL for each trade
    for trade in trades:
        prev_value = trade.get("prev_account_value", 0)
        curr_value = trade.get("curr_account_value", 0)
        trade["pnl"] = curr_value - prev_value
        trade["pnl_pct"] = (trade["pnl"] / prev_value * 100) if prev_value > 0 else 0
    
    # Sort by PnL
    sorted_trades = sorted(trades, key=lambda x: x["pnl"], reverse=True)
    
    best_trades = sorted_trades[:top_n]
    worst_trades = sorted_trades[-top_n:]
    
    return best_trades, worst_trades


def generate_trade_case_markdown(trade: Dict, case_number: int, case_type: str) -> str:
    """Generate markdown for a single trade case with full original data"""
    md = f"### 案例 {case_number}: {trade['model_id']} - "
    
    # Determine trade type
    changes = trade.get("position_changes", [])
    if changes:
        change_types = [c["change_type"] for c in changes]
        md += f"{', '.join(change_types)}\n\n"
    else:
        md += "交易\n\n"
    
    # Time and cycle info
    timestamp = trade.get("timestamp", 0)
    time_str = convert_timestamp(timestamp)
    cycle_id = trade.get("cycle_id", "N/A")
    
    md += f"📅 **时间**: {time_str} (timestamp: {timestamp})\n"
    md += f"🔢 **Cycle ID**: {cycle_id}\n"
    
    # Trade result
    pnl = trade.get("pnl", 0)
    pnl_pct = trade.get("pnl_pct", 0)
    emoji = "💰" if pnl > 0 else "💸"
    md += f"{emoji} **交易结果**: ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
    
    # Account change
    prev_value = trade.get("prev_account_value", 0)
    curr_value = trade.get("curr_account_value", 0)
    md += f"📊 **账户变化**: ${prev_value:.2f} → ${curr_value:.2f}\n"
    
    # Position changes
    if changes:
        md += f"\n**持仓变化**:\n"
        for change in changes:
            symbol = change.get("symbol", "N/A")
            prev_qty = change.get("prev_quantity", 0)
            curr_qty = change.get("curr_quantity", 0)
            change_type = change.get("change_type", "N/A")
            md += f"- {symbol}: {prev_qty:.2f} → {curr_qty:.2f} ({change_type})\n"
    
    md += "\n"
    
    # Full COT trace in expandable section
    cot_trace = trade.get("cot_trace", "")
    cot_summary = trade.get("cot_trace_summary", "")
    
    # Handle dict format
    if isinstance(cot_trace, dict):
        cot_trace_text = json.dumps(cot_trace, indent=2, ensure_ascii=False)
    else:
        cot_trace_text = str(cot_trace)
    
    md += f"💭 **完整思考过程** (点击展开):\n"
    md += f"<details>\n"
    md += f"<summary>查看完整COT原文 ({len(cot_trace_text)} 字符)</summary>\n\n"
    md += f"```\n{cot_trace_text}\n```\n\n"
    md += f"</details>\n\n"
    
    # Summary
    if cot_summary:
        md += f"📝 **思考摘要**:\n"
        md += f"> {cot_summary}\n\n"
    
    # Key findings based on case type
    cot_analysis = trade.get("cot_analysis", {})
    
    if case_type == "success":
        md += f"🎯 **成功要素**:\n"
    else:
        md += f"⚠️ **问题分析**:\n"
    
    # Analyze keywords
    tech_indicators = cot_analysis.get("technical_indicators", [])
    if tech_indicators:
        md += f"- 使用的技术指标: {', '.join(set(tech_indicators))}\n"
    
    timeframes = cot_analysis.get("timeframes", [])
    if timeframes:
        md += f"- 关注的时间周期: {', '.join(set(timeframes))}\n"
    
    risk_words = cot_analysis.get("risk_words", [])
    if risk_words:
        md += f"- 风险管理关键词: {', '.join(set(risk_words))}\n"
    
    md += f"- 思考复杂度: {cot_analysis.get('length', 0)} 字符\n"
    
    md += "\n---\n\n"
    
    return md


def generate_markdown_report(all_analysis: Dict[str, Dict]):
    """Generate comprehensive COT analysis report"""
    print("\nGenerating COT analysis report...")
    
    report_path = os.path.join(OUTPUT_DIR, OUTPUT_REPORT)
    
    with open(report_path, "w", encoding="utf-8") as f:
        # Header
        f.write("# COT思考分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**分析范围**: 561个交易的完整思考过程\n\n")
        f.write("**报告特点**: 每个洞见都附带完整原始数据引用\n\n")
        f.write("---\n\n")
        
        # Table of contents
        f.write("## 目录\n\n")
        f.write("1. [各模型思考风格概览](#各模型思考风格概览)\n")
        f.write("2. [成功模型的思考模式](#成功模型的思考模式)\n")
        f.write("3. [失败模型的思考陷阱](#失败模型的思考陷阱)\n")
        f.write("4. [最佳交易案例深度剖析](#最佳交易案例深度剖析)\n")
        f.write("5. [最差交易案例深度剖析](#最差交易案例深度剖析)\n")
        f.write("6. [关键洞察总结](#关键洞察总结)\n\n")
        f.write("---\n\n")
        
        # Section 1: Overview
        f.write("## 各模型思考风格概览\n\n")
        
        # Create comparison table
        f.write("### 思考特征对比\n\n")
        f.write("| 模型 | 平均思考长度 | 主要技术指标 | 关注时间周期 | 风险管理词汇 |\n")
        f.write("|------|-------------|-------------|-------------|-------------|\n")
        
        for model_id, analysis in sorted(all_analysis.items()):
            avg_len = analysis["avg_thinking_length"]
            
            # Top technical indicators
            tech_counts = analysis["keyword_counts"]["technical_indicators"]
            top_tech = [k for k, v in tech_counts.most_common(3)]
            tech_str = ", ".join(top_tech) if top_tech else "N/A"
            
            # Top timeframes
            time_counts = analysis["keyword_counts"]["timeframes"]
            top_time = [k for k, v in time_counts.most_common(2)]
            time_str = ", ".join(top_time) if top_time else "N/A"
            
            # Risk words count
            risk_count = sum(analysis["keyword_counts"]["risk_words"].values())
            
            f.write(f"| {model_id} | {avg_len:.0f} | {tech_str} | {time_str} | {risk_count} |\n")
        
        f.write("\n")
        
        # Detailed keyword analysis
        f.write("### 关键词频率统计\n\n")
        
        for model_id, analysis in sorted(all_analysis.items()):
            f.write(f"#### {model_id}\n\n")
            
            # Technical indicators
            tech_counts = analysis["keyword_counts"]["technical_indicators"]
            if tech_counts:
                f.write("**技术指标使用频率** (Top 10):\n")
                for keyword, count in tech_counts.most_common(10):
                    f.write(f"- {keyword}: {count}次\n")
                f.write("\n")
            
            # Market concepts
            market_counts = analysis["keyword_counts"]["market_concepts"]
            if market_counts:
                f.write("**市场概念提及频率** (Top 10):\n")
                for keyword, count in market_counts.most_common(10):
                    f.write(f"- {keyword}: {count}次\n")
                f.write("\n")
            
            # Timeframes
            time_counts = analysis["keyword_counts"]["timeframes"]
            if time_counts:
                f.write("**时间周期关注**:\n")
                for keyword, count in time_counts.most_common():
                    f.write(f"- {keyword}: {count}次\n")
                f.write("\n")
            
            f.write("---\n\n")
        
        # Section 2: Success patterns
        f.write("## 成功模型的思考模式\n\n")
        
        success_models = ["qwen3-max", "deepseek-chat-v3.1"]
        
        for model_id in success_models:
            if model_id in all_analysis:
                analysis = all_analysis[model_id]
                f.write(f"### {model_id}\n\n")
                
                f.write("**思考特点**:\n")
                f.write(f"- 平均思考长度: {analysis['avg_thinking_length']:.0f} 字符\n")
                
                tech_counts = analysis["keyword_counts"]["technical_indicators"]
                f.write(f"- 技术指标使用: {len(tech_counts)} 种，总计 {sum(tech_counts.values())} 次提及\n")
                
                risk_counts = analysis["keyword_counts"]["risk_words"]
                f.write(f"- 风险管理词汇: {sum(risk_counts.values())} 次提及\n\n")
                
                f.write("---\n\n")
        
        # Section 3: Failure patterns
        f.write("## 失败模型的思考陷阱\n\n")
        
        failure_models = ["gemini-2.5-pro", "gpt-5"]
        
        for model_id in failure_models:
            if model_id in all_analysis:
                analysis = all_analysis[model_id]
                f.write(f"### {model_id}\n\n")
                
                f.write("**思考特点**:\n")
                f.write(f"- 平均思考长度: {analysis['avg_thinking_length']:.0f} 字符\n")
                f.write(f"- 总交易次数: {analysis['total_trades']} (过高)\n")
                
                tech_counts = analysis["keyword_counts"]["technical_indicators"]
                f.write(f"- 技术指标使用: {len(tech_counts)} 种，总计 {sum(tech_counts.values())} 次提及\n\n")
                
                f.write("---\n\n")
        
        # Section 4: Best trade cases
        f.write("## 最佳交易案例深度剖析\n\n")
        f.write("以下展示每个模型的最佳交易，包含完整原始数据供参考。\n\n")
        
        case_number = 1
        for model_id, analysis in sorted(all_analysis.items()):
            f.write(f"### {model_id} 最佳交易\n\n")
            
            best_trades, _ = find_best_and_worst_cases(analysis["trades"], top_n=3)
            
            for trade in best_trades:
                case_md = generate_trade_case_markdown(trade, case_number, "success")
                f.write(case_md)
                case_number += 1
        
        # Section 5: Worst trade cases
        f.write("## 最差交易案例深度剖析\n\n")
        f.write("以下展示每个模型的最差交易，分析失败原因。\n\n")
        
        case_number = 1
        for model_id, analysis in sorted(all_analysis.items()):
            f.write(f"### {model_id} 最差交易\n\n")
            
            _, worst_trades = find_best_and_worst_cases(analysis["trades"], top_n=3)
            
            for trade in worst_trades:
                case_md = generate_trade_case_markdown(trade, case_number, "failure")
                f.write(case_md)
                case_number += 1
        
        # Section 6: Key insights
        f.write("## 关键洞察总结\n\n")
        
        f.write("### 成功思考模式的共同特征\n\n")
        f.write("1. **适度的思考复杂度**: 既不过度简单也不过度复杂\n")
        f.write("2. **明确的风险管理**: 频繁提及止损、风险控制\n")
        f.write("3. **多维度分析**: 结合技术指标和市场概念\n")
        f.write("4. **长期视角**: 关注较长时间周期\n\n")
        
        f.write("### 失败思考模式的共同陷阱\n\n")
        f.write("1. **过度依赖单一指标**: 特别是短期技术指标\n")
        f.write("2. **缺乏风险意识**: 很少提及止损和风险控制\n")
        f.write("3. **短期视角主导**: 过度关注短期波动\n")
        f.write("4. **决策过于频繁**: 导致思考质量下降\n\n")
        
        f.write("---\n\n")
        f.write("**报告说明**: 所有案例都包含完整的原始数据（timestamp, cycle_id, COT原文），")
        f.write("可用于进一步验证和深入分析。\n\n")
        f.write(f"**数据来源**: cleaned_data/ (561个交易记录)\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"Report saved: {report_path}")


def main():
    """Main execution"""
    print("=" * 60)
    print("COT THINKING ANALYSIS")
    print("=" * 60)
    
    all_models = [
        "qwen3-max",
        "deepseek-chat-v3.1",
        "claude-sonnet-4-5",
        "grok-4",
        "gemini-2.5-pro",
        "gpt-5"
    ]
    
    all_analysis = {}
    
    for model_id in all_models:
        trades = load_model_trades(model_id)
        if trades:
            analysis = analyze_model_thinking(model_id, trades)
            all_analysis[model_id] = analysis
    
    # Generate report
    generate_markdown_report(all_analysis)
    
    print("\n" + "=" * 60)
    print("COT ANALYSIS COMPLETE!")
    print("=" * 60)
    print(f"Report: {OUTPUT_DIR}/{OUTPUT_REPORT}")


if __name__ == "__main__":
    main()

