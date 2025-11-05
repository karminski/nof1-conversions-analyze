import json
import os
from collections import defaultdict
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Configuration
CLEANED_DATA_DIR = "cleaned_data"
OUTPUT_DIR = "DOCUMENTS"
OUTPUT_REPORT = "STRATEGY_ANALYSIS_REPORT.md"

# Model performance data (from previous analysis)
MODEL_PERFORMANCE = {
    "qwen3-max": {"final_return": 42.89, "style": "Long-term holding"},
    "deepseek-chat-v3.1": {"final_return": 26.82, "style": "Balanced trading"},
    "claude-sonnet-4-5": {"final_return": -12.79, "style": "Conservative multi"},
    "grok-4": {"final_return": -14.93, "style": "Mixed long/short"},
    "gemini-2.5-pro": {"final_return": -63.49, "style": "All-in short"},
    "gpt-5": {"final_return": -72.93, "style": "Chaotic trading"},
}


def load_model_trades(model_id: str) -> List[Dict]:
    """Load trades for a specific model"""
    filepath = os.path.join(CLEANED_DATA_DIR, f"{model_id}_trades.json")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {model_id}: {e}")
        return []


def calculate_trade_pnl(trade: Dict) -> Dict:
    """Calculate profit/loss for a trade"""
    prev_value = trade.get("prev_account_value", 0)
    curr_value = trade.get("curr_account_value", 0)
    
    pnl = curr_value - prev_value
    pnl_pct = (pnl / prev_value * 100) if prev_value > 0 else 0
    
    return {
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "is_profit": pnl > 0,
        "prev_value": prev_value,
        "curr_value": curr_value,
    }


def analyze_model_trades(model_id: str) -> Dict:
    """Analyze all trades for a model"""
    print(f"\nAnalyzing {model_id}...")
    
    trades = load_model_trades(model_id)
    if not trades:
        return None
    
    # Calculate PnL for each trade
    trades_with_pnl = []
    for trade in trades:
        pnl_info = calculate_trade_pnl(trade)
        trade_enhanced = {**trade, **pnl_info}
        trades_with_pnl.append(trade_enhanced)
    
    # Statistics
    total_trades = len(trades_with_pnl)
    profitable_trades = [t for t in trades_with_pnl if t["is_profit"]]
    losing_trades = [t for t in trades_with_pnl if not t["is_profit"]]
    
    win_rate = len(profitable_trades) / total_trades if total_trades > 0 else 0
    
    avg_profit = (
        sum(t["pnl"] for t in profitable_trades) / len(profitable_trades)
        if profitable_trades
        else 0
    )
    avg_loss = (
        sum(t["pnl"] for t in losing_trades) / len(losing_trades)
        if losing_trades
        else 0
    )
    
    profit_factor = abs(avg_profit / avg_loss) if avg_loss != 0 else float("inf")
    
    # Sort by PnL
    trades_sorted = sorted(trades_with_pnl, key=lambda x: x["pnl"], reverse=True)
    
    # Top 3 best and worst
    best_trades = trades_sorted[:3]
    worst_trades = trades_sorted[-3:]
    
    print(f"  Total trades: {total_trades}")
    print(f"  Win rate: {win_rate*100:.1f}%")
    print(f"  Avg profit: ${avg_profit:.2f}")
    print(f"  Avg loss: ${avg_loss:.2f}")
    
    return {
        "model_id": model_id,
        "total_trades": total_trades,
        "profitable_trades": len(profitable_trades),
        "losing_trades": len(losing_trades),
        "win_rate": win_rate,
        "avg_profit": avg_profit,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "total_pnl": sum(t["pnl"] for t in trades_with_pnl),
        "best_trades": best_trades,
        "worst_trades": worst_trades,
        "all_trades": trades_with_pnl,
    }


def extract_trade_features(trade: Dict) -> Dict:
    """Extract key features from a trade"""
    features = {
        "symbols": [],
        "change_types": [],
        "leverages": [],
        "directions": [],
    }
    
    # Extract from position changes
    for change in trade.get("position_changes", []):
        features["symbols"].append(change.get("symbol"))
        features["change_types"].append(change.get("change_type"))
        
        # Get leverage and direction from position details
        pos_details = change.get("position_details", {})
        if pos_details:
            features["leverages"].append(pos_details.get("leverage"))
            qty = change.get("curr_quantity", 0)
            features["directions"].append("long" if qty > 0 else "short" if qty < 0 else "flat")
    
    return features


def generate_trade_summary(trade: Dict) -> str:
    """Generate a human-readable summary of a trade"""
    changes = trade.get("position_changes", [])
    if not changes:
        return "No position changes"
    
    summary_parts = []
    for change in changes:
        symbol = change["symbol"]
        change_type = change["change_type"]
        prev_qty = change["prev_quantity"]
        curr_qty = change["curr_quantity"]
        
        summary_parts.append(
            f"{symbol}: {prev_qty:.2f} → {curr_qty:.2f} ({change_type})"
        )
    
    return "; ".join(summary_parts)


def analyze_all_models() -> Dict[str, Dict]:
    """Analyze all models"""
    print("=" * 60)
    print("ANALYZING ALL MODELS")
    print("=" * 60)
    
    all_results = {}
    
    for model_id in MODEL_PERFORMANCE.keys():
        result = analyze_model_trades(model_id)
        if result:
            all_results[model_id] = result
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    
    return all_results


def generate_markdown_report(analysis_results: Dict[str, Dict]):
    """Generate comprehensive Markdown report"""
    print("\nGenerating report...")
    
    report_path = os.path.join(OUTPUT_DIR, OUTPUT_REPORT)
    
    with open(report_path, "w", encoding="utf-8") as f:
        # Header
        f.write("# 深度策略分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**分析范围**: 561个交易记录，6个AI交易模型\n\n")
        f.write("---\n\n")
        
        # Table of Contents
        f.write("## 目录\n\n")
        f.write("1. [执行摘要](#执行摘要)\n")
        f.write("2. [模型综合对比](#模型综合对比)\n")
        f.write("3. [最佳交易深度剖析](#最佳交易深度剖析)\n")
        f.write("4. [最差交易深度剖析](#最差交易深度剖析)\n")
        f.write("5. [策略模式对比](#策略模式对比)\n")
        f.write("6. [关键洞察与建议](#关键洞察与建议)\n\n")
        f.write("---\n\n")
        
        # 1. Executive Summary
        f.write("## 执行摘要\n\n")
        f.write("本报告深度分析了6个AI交易模型的561个交易记录，识别成功和失败的策略模式。\n\n")
        
        # Sort models by final return
        sorted_models = sorted(
            analysis_results.items(),
            key=lambda x: MODEL_PERFORMANCE[x[0]]["final_return"],
            reverse=True,
        )
        
        f.write("### 模型表现排名\n\n")
        f.write("| 排名 | 模型 | 最终收益率 | 总交易数 | 胜率 | 盈亏比 |\n")
        f.write("|------|------|-----------|---------|------|--------|\n")
        
        for rank, (model_id, result) in enumerate(sorted_models, 1):
            final_return = MODEL_PERFORMANCE[model_id]["final_return"]
            win_rate = result["win_rate"] * 100
            profit_factor = result["profit_factor"]
            
            emoji = "🏆" if rank == 1 else "🥈" if rank == 2 else "📉" if final_return < 0 else "📊"
            
            f.write(
                f"| {rank} {emoji} | **{model_id}** | "
                f"{final_return:+.2f}% | {result['total_trades']} | "
                f"{win_rate:.1f}% | {profit_factor:.2f} |\n"
            )
        
        f.write("\n")
        
        # Key findings
        f.write("### 核心发现\n\n")
        
        # Find best and worst performers
        best_model = sorted_models[0][0]
        worst_model = sorted_models[-1][0]
        
        best_result = analysis_results[best_model]
        worst_result = analysis_results[worst_model]
        
        f.write(f"**最佳表现**: {best_model}\n")
        f.write(f"- 收益率: {MODEL_PERFORMANCE[best_model]['final_return']:+.2f}%\n")
        f.write(f"- 交易次数: {best_result['total_trades']}\n")
        f.write(f"- 胜率: {best_result['win_rate']*100:.1f}%\n")
        f.write(f"- 策略风格: {MODEL_PERFORMANCE[best_model]['style']}\n\n")
        
        f.write(f"**最差表现**: {worst_model}\n")
        f.write(f"- 收益率: {MODEL_PERFORMANCE[worst_model]['final_return']:+.2f}%\n")
        f.write(f"- 交易次数: {worst_result['total_trades']}\n")
        f.write(f"- 胜率: {worst_result['win_rate']*100:.1f}%\n")
        f.write(f"- 策略风格: {MODEL_PERFORMANCE[worst_model]['style']}\n\n")
        
        f.write("---\n\n")
        
        # 2. Model Comparison
        f.write("## 模型综合对比\n\n")
        
        for model_id, result in sorted_models:
            perf = MODEL_PERFORMANCE[model_id]
            
            f.write(f"### {model_id}\n\n")
            f.write(f"**收益率**: {perf['final_return']:+.2f}%  \n")
            f.write(f"**策略风格**: {perf['style']}\n\n")
            
            f.write("**交易统计**:\n")
            f.write(f"- 总交易数: {result['total_trades']}\n")
            f.write(f"- 盈利交易: {result['profitable_trades']} ({result['win_rate']*100:.1f}%)\n")
            f.write(f"- 亏损交易: {result['losing_trades']} ({(1-result['win_rate'])*100:.1f}%)\n")
            f.write(f"- 平均单笔盈利: ${result['avg_profit']:.2f}\n")
            f.write(f"- 平均单笔亏损: ${result['avg_loss']:.2f}\n")
            f.write(f"- 盈亏比: {result['profit_factor']:.2f}\n\n")
            
            # Best trade preview
            if result['best_trades']:
                best = result['best_trades'][0]
                f.write(f"**最佳单笔交易**: ${best['pnl']:.2f} ({best['pnl_pct']:+.2f}%)\n")
                f.write(f"- Cycle: {best['cycle_id']}\n")
                f.write(f"- 操作: {generate_trade_summary(best)}\n\n")
            
            # Worst trade preview
            if result['worst_trades']:
                worst = result['worst_trades'][-1]
                f.write(f"**最差单笔交易**: ${worst['pnl']:.2f} ({worst['pnl_pct']:+.2f}%)\n")
                f.write(f"- Cycle: {worst['cycle_id']}\n")
                f.write(f"- 操作: {generate_trade_summary(worst)}\n\n")
            
            f.write("---\n\n")
        
        # 3. Best Trades Deep Dive
        f.write("## 最佳交易深度剖析\n\n")
        f.write("分析每个模型的Top 3最大盈利交易，提取成功模式。\n\n")
        
        for model_id, result in sorted_models:
            f.write(f"### {model_id} - 最佳交易\n\n")
            
            for idx, trade in enumerate(result['best_trades'], 1):
                f.write(f"#### 最佳交易 #{idx}: +${trade['pnl']:.2f} ({trade['pnl_pct']:+.2f}%)\n\n")
                
                # Basic info
                f.write(f"**周期**: {trade['cycle_id']}  \n")
                f.write(f"**账户变化**: ${trade['prev_value']:.2f} → ${trade['curr_value']:.2f}  \n")
                f.write(f"**当前收益率**: {trade['account_info'].get('return_pct', 0):.2f}%\n\n")
                
                # Position changes
                f.write("**持仓变化**:\n")
                for change in trade.get('position_changes', []):
                    f.write(f"- {change['symbol']}: {change['prev_quantity']:.2f} → {change['curr_quantity']:.2f} ({change['change_type']})\n")
                    
                    pos_details = change.get('position_details', {})
                    if pos_details:
                        f.write(f"  - 杠杆: {pos_details.get('leverage', 'N/A')}x\n")
                        f.write(f"  - 入场价: ${pos_details.get('entry_price', 0):.2f}\n")
                        f.write(f"  - 当前价: ${pos_details.get('current_price', 0):.2f}\n")
                
                f.write("\n")
                
                # Strategy thinking
                cot_summary = trade.get('cot_trace_summary', '')
                if cot_summary:
                    f.write("**策略思考**:\n")
                    f.write(f"> {cot_summary}\n\n")
                
                # LLM response (decision)
                llm_response = trade.get('llm_response', {})
                if llm_response:
                    f.write("**交易决策**:\n")
                    for coin, decision in llm_response.items():
                        if isinstance(decision, dict):
                            signal = decision.get('signal', 'N/A')
                            confidence = decision.get('confidence', 'N/A')
                            leverage = decision.get('leverage', 'N/A')
                            f.write(f"- **{coin}**: {signal} (信心: {confidence}, 杠杆: {leverage}x)\n")
                            
                            justification = decision.get('justification', '')
                            if justification:
                                f.write(f"  - 理由: {justification[:200]}...\n")
                
                f.write("\n---\n\n")
        
        # 4. Worst Trades Deep Dive
        f.write("## 最差交易深度剖析\n\n")
        f.write("分析每个模型的Top 3最大亏损交易，提取失败教训。\n\n")
        
        for model_id, result in sorted_models:
            f.write(f"### {model_id} - 最差交易\n\n")
            
            worst_trades_sorted = sorted(result['worst_trades'], key=lambda x: x['pnl'])
            
            for idx, trade in enumerate(worst_trades_sorted, 1):
                f.write(f"#### 最差交易 #{idx}: ${trade['pnl']:.2f} ({trade['pnl_pct']:+.2f}%)\n\n")
                
                # Basic info
                f.write(f"**周期**: {trade['cycle_id']}  \n")
                f.write(f"**账户变化**: ${trade['prev_value']:.2f} → ${trade['curr_value']:.2f}  \n")
                f.write(f"**当前收益率**: {trade['account_info'].get('return_pct', 0):.2f}%\n\n")
                
                # Position changes
                f.write("**持仓变化**:\n")
                for change in trade.get('position_changes', []):
                    f.write(f"- {change['symbol']}: {change['prev_quantity']:.2f} → {change['curr_quantity']:.2f} ({change['change_type']})\n")
                    
                    pos_details = change.get('position_details', {})
                    if pos_details:
                        f.write(f"  - 杠杆: {pos_details.get('leverage', 'N/A')}x\n")
                
                f.write("\n")
                
                # Strategy thinking
                cot_summary = trade.get('cot_trace_summary', '')
                if cot_summary:
                    f.write("**策略思考**:\n")
                    f.write(f"> {cot_summary}\n\n")
                
                f.write("---\n\n")
        
        # 5. Strategy Pattern Comparison
        f.write("## 策略模式对比\n\n")
        
        f.write("### 盈利模型 vs 亏损模型\n\n")
        
        profitable_models = [m for m in sorted_models if MODEL_PERFORMANCE[m[0]]['final_return'] > 0]
        losing_models = [m for m in sorted_models if MODEL_PERFORMANCE[m[0]]['final_return'] < 0]
        
        f.write("#### 盈利模型特征\n\n")
        for model_id, result in profitable_models:
            f.write(f"**{model_id}** ({MODEL_PERFORMANCE[model_id]['final_return']:+.2f}%):\n")
            f.write(f"- 交易频率: {result['total_trades']}次（{'低' if result['total_trades'] < 50 else '中'}）\n")
            f.write(f"- 胜率: {result['win_rate']*100:.1f}%\n")
            f.write(f"- 盈亏比: {result['profit_factor']:.2f}\n")
            f.write(f"- 风格: {MODEL_PERFORMANCE[model_id]['style']}\n\n")
        
        f.write("#### 亏损模型特征\n\n")
        for model_id, result in losing_models:
            f.write(f"**{model_id}** ({MODEL_PERFORMANCE[model_id]['final_return']:+.2f}%):\n")
            f.write(f"- 交易频率: {result['total_trades']}次（{'高' if result['total_trades'] > 100 else '中'}）\n")
            f.write(f"- 胜率: {result['win_rate']*100:.1f}%\n")
            f.write(f"- 盈亏比: {result['profit_factor']:.2f}\n")
            f.write(f"- 风格: {MODEL_PERFORMANCE[model_id]['style']}\n\n")
        
        f.write("---\n\n")
        
        # 6. Key Insights and Recommendations
        f.write("## 关键洞察与建议\n\n")
        
        f.write("### 成功要素\n\n")
        f.write("1. **交易频率控制**: 盈利模型平均交易次数显著少于亏损模型\n")
        f.write("   - qwen3-max: 37次 → +42.89%\n")
        f.write("   - gemini-2.5-pro: 237次 → -63.49%\n\n")
        
        f.write("2. **长期持仓策略**: 最成功的模型倾向于长期持有盈利仓位\n\n")
        
        f.write("3. **风险管理**: 盈利模型展现出更好的风险控制\n\n")
        
        f.write("### 失败教训\n\n")
        f.write("1. **过度交易**: 频繁交易导致交易成本累积和决策疲劳\n\n")
        
        f.write("2. **情绪化决策**: 亏损模型更容易在不利情况下频繁调整仓位\n\n")
        
        f.write("3. **缺乏耐心**: 未能给盈利仓位足够的时间发展\n\n")
        
        f.write("### 可行建议\n\n")
        f.write("1. **减少交易频率**: 专注于高质量交易机会\n")
        f.write("2. **趋势跟踪**: 识别并持有符合大趋势的仓位\n")
        f.write("3. **严格止损**: 设置明确的止损位并严格执行\n")
        f.write("4. **避免报复性交易**: 亏损后不要急于通过更多交易弥补\n")
        f.write("5. **资金管理**: 合理控制单笔交易的风险敞口\n\n")
        
        f.write("---\n\n")
        f.write("**报告生成**: {}\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        f.write("**数据来源**: cleaned_data/ (561个交易记录)\n")
    
    print(f"Report saved: {report_path}")


def main():
    """Main execution"""
    print("=" * 60)
    print("DEEP STRATEGY ANALYSIS")
    print("=" * 60)
    
    # Analyze all models
    results = analyze_all_models()
    
    # Generate report
    generate_markdown_report(results)
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE!")
    print("=" * 60)
    print(f"Report: {OUTPUT_DIR}/{OUTPUT_REPORT}")


if __name__ == "__main__":
    main()

