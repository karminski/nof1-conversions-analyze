import json
import os
from datetime import datetime
from typing import Dict, List

# Configuration
CLEANED_DATA_DIR = "cleaned_data"
OUTPUT_HTML = "trading_timeline_viz.html"

# Model colors
MODEL_COLORS = {
    "qwen3-max": "#00C853",
    "deepseek-chat-v3.1": "#2196F3",
    "gpt-5": "#F44336",
    "claude-sonnet-4-5": "#9C27B0",
    "gemini-2.5-pro": "#FF9800",
    "grok-4": "#607D8B",
}


def load_all_trades() -> List[Dict]:
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
                # Add model info and calculate PnL
                for trade in trades:
                    trade["model_id"] = model_id
                    trade["model_color"] = MODEL_COLORS.get(model_id, "#000000")
                    
                    # Calculate PnL
                    prev_value = trade.get("prev_account_value", 0)
                    curr_value = trade.get("curr_account_value", 0)
                    trade["pnl"] = curr_value - prev_value
                    trade["pnl_pct"] = (trade["pnl"] / prev_value * 100) if prev_value > 0 else 0
                    
                all_trades.extend(trades)
                print(f"Loaded {len(trades)} trades from {model_id}")
        except Exception as e:
            print(f"Error loading {model_id}: {e}")
    
    # Sort by timestamp
    all_trades.sort(key=lambda x: x.get("timestamp", 0))
    
    print(f"\nTotal trades loaded: {len(all_trades)}")
    return all_trades


def format_trade_for_js(trade: Dict) -> Dict:
    """Format trade data for JavaScript"""
    timestamp = trade.get("timestamp", 0)
    
    # Get position changes summary
    changes = trade.get("position_changes", [])
    change_summary = []
    total_notional = 0
    
    for change in changes:
        symbol = change.get("symbol", "")
        prev_qty = change.get("prev_quantity", 0)
        curr_qty = change.get("curr_quantity", 0)
        change_type = change.get("change_type", "")
        
        pos_details = change.get("position_details", {})
        price = pos_details.get("current_price", 0)
        leverage = pos_details.get("leverage", 1)
        
        notional = abs(curr_qty * price)
        total_notional += notional
        
        change_summary.append({
            "symbol": symbol,
            "from": prev_qty,
            "to": curr_qty,
            "type": change_type,
            "price": price,
            "leverage": leverage,
            "notional": notional
        })
    
    # Get thinking summary
    cot_summary = trade.get("cot_trace_summary", "")
    if len(cot_summary) > 150:
        cot_summary = cot_summary[:150] + "..."
    
    return {
        "timestamp": timestamp * 1000,  # Convert to milliseconds for JS
        "date": datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        "model": trade.get("model_id", ""),
        "color": trade.get("model_color", "#000"),
        "cycle": trade.get("cycle_id", 0),
        "pnl": round(trade.get("pnl", 0), 2),
        "pnl_pct": round(trade.get("pnl_pct", 0), 2),
        "account_value": round(trade.get("curr_account_value", 0), 2),
        "changes": change_summary,
        "total_notional": round(total_notional, 2),
        "thinking": cot_summary,
        "return_pct": round(trade.get("account_info", {}).get("return_pct", 0), 2)
    }


def generate_html(trades_data: List[Dict]):
    """Generate interactive HTML visualization"""
    
    # Prepare data for JavaScript
    js_trades = [format_trade_for_js(trade) for trade in trades_data]
    
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI交易历史可视化</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        
        .header p {{
            font-size: 16px;
            opacity: 0.9;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            font-size: 14px;
            color: #666;
        }}
        
        .filters {{
            padding: 20px 30px;
            background: white;
            border-bottom: 2px solid #f0f0f0;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .filter-group label {{
            font-weight: 600;
            color: #333;
        }}
        
        .model-checkbox {{
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 5px 15px;
            border-radius: 20px;
            background: #f8f9fa;
            cursor: pointer;
            transition: all 0.3s;
        }}
        
        .model-checkbox:hover {{
            background: #e9ecef;
        }}
        
        .model-checkbox input {{
            cursor: pointer;
        }}
        
        .color-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }}
        
        .chart-container {{
            padding: 30px;
            position: relative;
            height: 600px;
        }}
        
        .trade-details {{
            padding: 30px;
            background: #f8f9fa;
            border-top: 2px solid #e9ecef;
            display: none;
        }}
        
        .trade-details.active {{
            display: block;
        }}
        
        .trade-card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        
        .trade-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }}
        
        .trade-title {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }}
        
        .trade-pnl {{
            font-size: 24px;
            font-weight: bold;
        }}
        
        .trade-pnl.positive {{
            color: #00C853;
        }}
        
        .trade-pnl.negative {{
            color: #F44336;
        }}
        
        .trade-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .info-item {{
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        
        .info-label {{
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }}
        
        .info-value {{
            font-size: 16px;
            font-weight: 600;
            color: #333;
        }}
        
        .trade-changes {{
            margin: 20px 0;
        }}
        
        .change-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 10px;
        }}
        
        .change-symbol {{
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
        }}
        
        .change-type {{
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: 600;
            background: #e3f2fd;
            color: #1976d2;
        }}
        
        .trade-thinking {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        
        .thinking-label {{
            font-size: 14px;
            font-weight: 600;
            color: #666;
            margin-bottom: 10px;
        }}
        
        .thinking-text {{
            font-size: 15px;
            line-height: 1.6;
            color: #333;
            font-style: italic;
        }}
        
        .legend {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            padding: 20px 30px;
            background: #f8f9fa;
            border-top: 2px solid #e9ecef;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        @media (max-width: 768px) {{
            .stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .chart-container {{
                height: 400px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI交易历史时间轴</h1>
            <p>6个AI模型 × 561个真实交易 × 11天交易历史</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="total-trades">561</div>
                <div class="stat-label">总交易数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="total-models">6</div>
                <div class="stat-label">AI模型</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="date-range">11天</div>
                <div class="stat-label">交易周期</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="profit-trades">-</div>
                <div class="stat-label">盈利交易</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="loss-trades">-</div>
                <div class="stat-label">亏损交易</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="win-rate">-</div>
                <div class="stat-label">总胜率</div>
            </div>
        </div>
        
        <div class="filters">
            <div class="filter-group">
                <label>筛选模型:</label>
            </div>
            <label class="model-checkbox">
                <input type="checkbox" class="model-filter" data-model="qwen3-max" checked>
                <span class="color-dot" style="background: #00C853;"></span>
                <span>qwen3-max</span>
            </label>
            <label class="model-checkbox">
                <input type="checkbox" class="model-filter" data-model="deepseek-chat-v3.1" checked>
                <span class="color-dot" style="background: #2196F3;"></span>
                <span>deepseek-chat-v3.1</span>
            </label>
            <label class="model-checkbox">
                <input type="checkbox" class="model-filter" data-model="claude-sonnet-4-5" checked>
                <span class="color-dot" style="background: #9C27B0;"></span>
                <span>claude-sonnet-4-5</span>
            </label>
            <label class="model-checkbox">
                <input type="checkbox" class="model-filter" data-model="grok-4" checked>
                <span class="color-dot" style="background: #607D8B;"></span>
                <span>grok-4</span>
            </label>
            <label class="model-checkbox">
                <input type="checkbox" class="model-filter" data-model="gemini-2.5-pro" checked>
                <span class="color-dot" style="background: #FF9800;"></span>
                <span>gemini-2.5-pro</span>
            </label>
            <label class="model-checkbox">
                <input type="checkbox" class="model-filter" data-model="gpt-5" checked>
                <span class="color-dot" style="background: #F44336;"></span>
                <span>gpt-5</span>
            </label>
        </div>
        
        <div class="chart-container">
            <canvas id="tradeChart"></canvas>
        </div>
        
        <div class="trade-details" id="tradeDetails">
            <!-- Trade details will be populated here -->
        </div>
    </div>
    
    <script>
        // Trade data
        const allTrades = {json.dumps(js_trades, ensure_ascii=False)};
        
        let chart;
        let selectedModels = new Set(['qwen3-max', 'deepseek-chat-v3.1', 'claude-sonnet-4-5', 'grok-4', 'gemini-2.5-pro', 'gpt-5']);
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            updateStats();
            createChart();
            setupFilters();
        }});
        
        function updateStats() {{
            const visible = allTrades.filter(t => selectedModels.has(t.model));
            
            document.getElementById('total-trades').textContent = visible.length;
            
            const profitTrades = visible.filter(t => t.pnl > 0).length;
            const lossTrades = visible.filter(t => t.pnl < 0).length;
            const winRate = ((profitTrades / visible.length) * 100).toFixed(1);
            
            document.getElementById('profit-trades').textContent = profitTrades;
            document.getElementById('loss-trades').textContent = lossTrades;
            document.getElementById('win-rate').textContent = winRate + '%';
            
            if (visible.length > 0) {{
                const firstDate = new Date(visible[0].timestamp);
                const lastDate = new Date(visible[visible.length - 1].timestamp);
                const days = Math.ceil((lastDate - firstDate) / (1000 * 60 * 60 * 24));
                document.getElementById('date-range').textContent = days + '天';
            }}
        }}
        
        function createChart() {{
            const ctx = document.getElementById('tradeChart').getContext('2d');
            
            const filteredTrades = allTrades.filter(t => selectedModels.has(t.model));
            
            // Create datasets for each model
            const datasets = Array.from(selectedModels).map(model => {{
                const modelTrades = filteredTrades.filter(t => t.model === model);
                const color = modelTrades[0]?.color || '#000';
                
                return {{
                    label: model,
                    data: modelTrades.map(t => ({{
                        x: t.timestamp,
                        y: t.return_pct,
                        r: Math.max(5, Math.min(20, Math.abs(t.pnl) / 50)),
                        trade: t
                    }})),
                    backgroundColor: color + '80',
                    borderColor: color,
                    borderWidth: 2
                }};
            }});
            
            if (chart) {{
                chart.destroy();
            }}
            
            chart = new Chart(ctx, {{
                type: 'bubble',
                data: {{
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: '交易时间轴 (气泡大小=交易金额)',
                            font: {{
                                size: 18,
                                weight: 'bold'
                            }}
                        }},
                        legend: {{
                            display: true,
                            position: 'bottom'
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const trade = context.raw.trade;
                                    return [
                                        `${{trade.model}}`,
                                        `收益率: ${{trade.return_pct}}%`,
                                        `PnL: $${{trade.pnl}} (${{trade.pnl_pct}}%)`,
                                        `时间: ${{trade.date}}`,
                                        `点击查看详情`
                                    ];
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            type: 'time',
                            time: {{
                                unit: 'day',
                                displayFormats: {{
                                    day: 'MM-dd'
                                }}
                            }},
                            title: {{
                                display: true,
                                text: '时间'
                            }}
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: '账户收益率 (%)'
                            }},
                            ticks: {{
                                callback: function(value) {{
                                    return value + '%';
                                }}
                            }}
                        }}
                    }},
                    onClick: (event, elements) => {{
                        if (elements.length > 0) {{
                            const trade = elements[0].element.$context.raw.trade;
                            showTradeDetails(trade);
                        }}
                    }}
                }}
            }});
        }}
        
        function showTradeDetails(trade) {{
            const detailsDiv = document.getElementById('tradeDetails');
            
            const changesHTML = trade.changes.map(change => `
                <div class="change-item">
                    <div>
                        <div class="change-symbol">${{change.symbol}}</div>
                        <div style="font-size: 14px; color: #666; margin-top: 5px;">
                            ${{change.from.toFixed(2)}} → ${{change.to.toFixed(2)}}
                            (杠杆: ${{change.leverage}}x, 价格: $${{change.price.toFixed(2)}})
                        </div>
                    </div>
                    <div>
                        <span class="change-type">${{change.type}}</span>
                        <div style="font-size: 14px; color: #666; margin-top: 5px;">
                            名义金额: $${{change.notional.toFixed(2)}}
                        </div>
                    </div>
                </div>
            `).join('');
            
            detailsDiv.innerHTML = `
                <div class="trade-card">
                    <div class="trade-header">
                        <div>
                            <div class="trade-title">
                                <span class="color-dot" style="background: ${{trade.color}};"></span>
                                ${{trade.model}} - Cycle ${{trade.cycle}}
                            </div>
                            <div style="font-size: 14px; color: #666; margin-top: 5px;">
                                ${{trade.date}}
                            </div>
                        </div>
                        <div class="trade-pnl ${{trade.pnl >= 0 ? 'positive' : 'negative'}}">
                            $${{trade.pnl >= 0 ? '+' : ''}}${{trade.pnl}} (${{trade.pnl_pct >= 0 ? '+' : ''}}${{trade.pnl_pct}}%)
                        </div>
                    </div>
                    
                    <div class="trade-info">
                        <div class="info-item">
                            <div class="info-label">账户价值</div>
                            <div class="info-value">$${{trade.account_value.toLocaleString()}}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">总收益率</div>
                            <div class="info-value" style="color: ${{trade.return_pct >= 0 ? '#00C853' : '#F44336'}}">
                                ${{trade.return_pct >= 0 ? '+' : ''}}${{trade.return_pct}}%
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">交易金额</div>
                            <div class="info-value">$${{trade.total_notional.toLocaleString()}}</div>
                        </div>
                    </div>
                    
                    <div class="trade-changes">
                        <h3 style="margin-bottom: 15px; color: #333;">持仓变化</h3>
                        ${{changesHTML}}
                    </div>
                    
                    <div class="trade-thinking">
                        <div class="thinking-label">💭 AI思考摘要</div>
                        <div class="thinking-text">"${{trade.thinking}}"</div>
                    </div>
                </div>
            `;
            
            detailsDiv.classList.add('active');
            detailsDiv.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }}
        
        function setupFilters() {{
            document.querySelectorAll('.model-filter').forEach(checkbox => {{
                checkbox.addEventListener('change', function() {{
                    const model = this.dataset.model;
                    if (this.checked) {{
                        selectedModels.add(model);
                    }} else {{
                        selectedModels.delete(model);
                    }}
                    updateStats();
                    createChart();
                }});
            }});
        }}
    </script>
</body>
</html>'''
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"\nHTML visualization generated: {OUTPUT_HTML}")
    print(f"Total trades included: {len(js_trades)}")
    print(f"\nOpen {OUTPUT_HTML} in your web browser to view the interactive timeline!")


def main():
    """Main execution"""
    print("=" * 60)
    print("GENERATING TRADING TIMELINE VISUALIZATION")
    print("=" * 60)
    
    # Load all trades
    all_trades = load_all_trades()
    
    # Generate HTML
    generate_html(all_trades)
    
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()

