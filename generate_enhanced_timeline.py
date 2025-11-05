import json
import os
from datetime import datetime
from typing import Dict, List

# Configuration
CLEANED_DATA_DIR = "cleaned_data"
BTC_DATA_FILE = "btc_price_data.json"
OUTPUT_HTML = "trading_timeline_with_btc.html"

# Model colors
MODEL_COLORS = {
    "qwen3-max": "rgb(139, 92, 246)",
    "deepseek-chat-v3.1": "rgb(77, 107, 254)",
    "gpt-5": "rgb(30, 168, 135)",
    "claude-sonnet-4-5": "rgb(201, 100, 66)",
    "gemini-2.5-pro": "rgb(66, 133, 244)",
    "grok-4": "#000000",
}


def load_all_trades() -> List[Dict]:
    """Load all trades from all models"""
    all_trades = []
    
    models = list(MODEL_COLORS.keys())
    
    for model_id in models:
        filepath = os.path.join(CLEANED_DATA_DIR, f"{model_id}_trades.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                trades = json.load(f)
                for trade in trades:
                    trade["model_id"] = model_id
                    trade["model_color"] = MODEL_COLORS.get(model_id, "#000000")
                    
                    prev_value = trade.get("prev_account_value", 0)
                    curr_value = trade.get("curr_account_value", 0)
                    trade["pnl"] = curr_value - prev_value
                    trade["pnl_pct"] = (trade["pnl"] / prev_value * 100) if prev_value > 0 else 0
                    
                all_trades.extend(trades)
        except Exception as e:
            print(f"Error loading {model_id}: {e}")
    
    all_trades.sort(key=lambda x: x.get("timestamp", 0))
    return all_trades


def load_btc_data() -> Dict:
    """Load BTC price data"""
    try:
        with open(BTC_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading BTC data: {e}")
        return {"raw_prices": [], "daily_candles": []}


def format_trade_for_js(trade: Dict) -> Dict:
    """Format trade data for JavaScript"""
    timestamp = trade.get("timestamp", 0)
    
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
    
    cot_summary = trade.get("cot_trace_summary", "")
    if len(cot_summary) > 150:
        cot_summary = cot_summary[:150] + "..."
    
    account_info = trade.get("account_info", {})
    
    return {
        "timestamp": timestamp * 1000,
        "date": datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        "model": trade.get("model_id", ""),
        "color": trade.get("model_color", "#000"),
        "cycle": trade.get("cycle_id", 0),
        "pnl": round(trade.get("pnl", 0), 2),
        "pnl_pct": round(trade.get("pnl_pct", 0), 2),
        "account_value": round(trade.get("curr_account_value", 0), 2),
        "available_cash": round(account_info.get("available_cash", 0), 2),
        "sharpe_ratio": round(account_info.get("sharpe_ratio", 0), 3),
        "changes": change_summary,
        "total_notional": round(total_notional, 2),
        "thinking": cot_summary,
        "return_pct": round(account_info.get("return_pct", 0), 2)
    }


def format_btc_data_for_js(btc_data: Dict) -> Dict:
    """Format BTC data for JavaScript"""
    raw_prices = btc_data.get("raw_prices", [])
    daily_candles = btc_data.get("daily_candles", [])
    
    # Format raw prices for line chart
    price_line = [{
        "x": p["timestamp"] * 1000,
        "y": p["price"]
    } for p in raw_prices]
    
    # Format daily candles
    candles = [{
        "x": c["timestamp"] * 1000,
        "date": c["date"],
        "o": c["open"],
        "h": c["high"],
        "l": c["low"],
        "c": c["close"],
        "count": c["count"]
    } for c in daily_candles]
    
    return {
        "line": price_line,
        "candles": candles
    }


def generate_html(trades_data: List[Dict], btc_data: Dict):
    """Generate enhanced HTML visualization with BTC price overlay"""
    
    js_trades = [format_trade_for_js(trade) for trade in trades_data]
    js_btc = format_btc_data_for_js(btc_data)
    
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI交易历史 + BTC价格走势</title>
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
            background: linear-gradient(135deg, #f5f5f7 0%, #e8e8ed 100%);
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
            background: linear-gradient(135deg, #f5f5f7 0%, #e8e8ed 100%);
            color: #1d1d1f;
            padding: 30px;
            text-align: center;
            border-bottom: 1px solid #d2d2d7;
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
            color: #1d1d1f;
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
        
        .btc-toggle {{
            margin-left: auto;
            padding: 8px 20px;
            background: #f7931a;
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }}
        
        .btc-toggle:hover {{
            background: #d67915;
        }}
        
        .btc-toggle.active {{
            background: #00C853;
        }}
        
        .chart-container {{
            padding: 30px;
            position: relative;
            height: 650px;
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
            color: #1d1d1f;
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
        
        .show-details-btn {{
            margin-top: 10px;
            padding: 8px 16px;
            background: #1d1d1f;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.3s;
        }}
        
        .show-details-btn:hover {{
            background: #424245;
            transform: translateY(-1px);
        }}
        
        .show-details-btn:active {{
            transform: translateY(0);
        }}
        
        .trade-details-full {{
            display: none;
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #d2d2d7;
        }}
        
        .trade-details-full.active {{
            display: block;
            animation: slideDown 0.3s ease-out;
        }}
        
        @keyframes slideDown {{
            from {{
                opacity: 0;
                transform: translateY(-10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .detail-section {{
            margin-bottom: 20px;
            background: white;
            padding: 15px;
            border-radius: 6px;
        }}
        
        .detail-section-title {{
            font-size: 16px;
            font-weight: bold;
            color: #1d1d1f;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #f0f0f0;
        }}
        
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f8f9fa;
        }}
        
        .detail-row:last-child {{
            border-bottom: none;
        }}
        
        .detail-key {{
            font-weight: 600;
            color: #666;
            font-size: 14px;
        }}
        
        .detail-value {{
            color: #1d1d1f;
            font-size: 14px;
            text-align: right;
            max-width: 60%;
            word-wrap: break-word;
        }}
        
        .cot-full-text {{
            background: #fff;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #ff9800;
            font-size: 14px;
            line-height: 1.8;
            color: #333;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 400px;
            overflow-y: auto;
        }}
        
        .loading-spinner {{
            text-align: center;
            padding: 20px;
            color: #666;
        }}
        
        .header a {{
            display: inline-block;
            margin-top: 10px;
            color: #007AFF;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        
        .header a:hover {{
            color: #0051D5;
            text-decoration: underline;
        }}
        
        .footer {{
            background: linear-gradient(135deg, #f5f5f7 0%, #e8e8ed 100%);
            padding: 40px 30px;
            text-align: center;
            border-top: 1px solid #d2d2d7;
        }}
        
        .footer-logo {{
            margin-bottom: 20px;
        }}
        
        .footer-logo img {{
            height: 60px;
            width: auto;
            opacity: 0.9;
            transition: opacity 0.3s ease;
        }}
        
        .footer-logo img:hover {{
            opacity: 1;
        }}
        
        .footer-text {{
            font-size: 14px;
            color: #666;
            margin-top: 15px;
        }}
        
        .footer-links {{
            margin-top: 15px;
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }}
        
        .footer-links a {{
            color: #007AFF;
            text-decoration: none;
            font-size: 13px;
            transition: color 0.3s ease;
        }}
        
        .footer-links a:hover {{
            color: #0051D5;
            text-decoration: underline;
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
            <h1>🤖 AI交易历史 + 📈 BTC价格走势</h1>
            <p>6个AI模型 × 561个交易 × BTC实时价格</p>
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
                <div class="stat-value" id="date-range">13天</div>
                <div class="stat-label">交易周期</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="btc-range">-</div>
                <div class="stat-label">BTC价格区间</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="profit-trades">-</div>
                <div class="stat-label">盈利交易</div>
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
            <button class="btc-toggle active" id="btcToggle" onclick="toggleBTC()">
                ₿ BTC价格: 显示
            </button>
        </div>
        
        <div class="chart-container">
            <canvas id="tradeChart"></canvas>
        </div>
        
        <div class="trade-details" id="tradeDetails">
            <!-- Trade details will be populated here -->
        </div>
    </div>
    
    <script>
        // Data
        const allTrades = {json.dumps(js_trades, ensure_ascii=False)};
        const btcData = {json.dumps(js_btc, ensure_ascii=False)};
        
        let chart;
        let selectedModels = new Set(['qwen3-max', 'deepseek-chat-v3.1', 'claude-sonnet-4-5', 'grok-4', 'gemini-2.5-pro', 'gpt-5']);
        let showBTC = true;
        
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
            document.getElementById('win-rate').textContent = winRate + '%';
            
            // BTC stats
            if (btcData.line && btcData.line.length > 0) {{
                const prices = btcData.line.map(p => p.y);
                const minPrice = Math.min(...prices);
                const maxPrice = Math.max(...prices);
                document.getElementById('btc-range').textContent = 
                    `$${{(minPrice/1000).toFixed(1)}}K-$${{(maxPrice/1000).toFixed(1)}}K`;
            }}
        }}
        
        function createChart() {{
            const ctx = document.getElementById('tradeChart').getContext('2d');
            
            const filteredTrades = allTrades.filter(t => selectedModels.has(t.model));
            
            // Create datasets for each model (bubble chart)
            const tradeDatasets = Array.from(selectedModels).map(model => {{
                const modelTrades = filteredTrades.filter(t => t.model === model);
                const color = modelTrades[0]?.color || '#000';
                
                return {{
                    type: 'bubble',
                    label: model,
                    data: modelTrades.map(t => ({{
                        x: t.timestamp,
                        y: t.return_pct,
                        r: Math.max(5, Math.min(20, Math.abs(t.pnl) / 50)),
                        trade: t
                    }})),
                    backgroundColor: color,
                    borderColor: color,
                    borderWidth: 2,
                    yAxisID: 'y'
                }};
            }});
            
            // BTC price dataset (line chart on secondary axis)
            const btcDataset = {{
                type: 'line',
                label: 'BTC Price',
                data: btcData.line,
                borderColor: '#f7931a',
                backgroundColor: 'rgba(247, 147, 26, 0.1)',
                borderWidth: 3,
                pointRadius: 0,
                fill: false,
                yAxisID: 'y2',
                hidden: !showBTC
            }};
            
            const datasets = showBTC ? [...tradeDatasets, btcDataset] : tradeDatasets;
            
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
                    interaction: {{
                        mode: 'nearest',
                        intersect: false
                    }},
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'AI交易时间轴 + BTC价格走势',
                            font: {{
                                size: 18,
                                weight: 'bold'
                            }}
                        }},
                        legend: {{
                            display: true,
                            position: 'bottom',
                            labels: {{
                                usePointStyle: true,
                                padding: 15
                            }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    if (context.dataset.type === 'line') {{
                                        return `BTC: $${{context.parsed.y.toLocaleString()}}`;
                                    }}
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
                                text: '时间',
                                font: {{
                                    size: 14,
                                    weight: 'bold'
                                }}
                            }},
                            grid: {{
                                color: 'rgba(0, 0, 0, 0.05)'
                            }}
                        }},
                        y: {{
                            type: 'linear',
                            position: 'left',
                            title: {{
                                display: true,
                                text: '账户收益率 (%)',
                                color: '#667eea',
                                font: {{
                                    size: 14,
                                    weight: 'bold'
                                }}
                            }},
                            ticks: {{
                                callback: function(value) {{
                                    return value + '%';
                                }},
                                color: '#667eea'
                            }},
                            grid: {{
                                color: 'rgba(102, 126, 234, 0.1)'
                            }}
                        }},
                        y2: {{
                            type: 'linear',
                            position: 'right',
                            display: showBTC,
                            title: {{
                                display: true,
                                text: 'BTC价格 ($)',
                                color: '#f7931a',
                                font: {{
                                    size: 14,
                                    weight: 'bold'
                                }}
                            }},
                            ticks: {{
                                callback: function(value) {{
                                    return '$' + (value/1000).toFixed(1) + 'K';
                                }},
                                color: '#f7931a'
                            }},
                            grid: {{
                                drawOnChartArea: false,
                                color: 'rgba(247, 147, 26, 0.1)'
                            }}
                        }}
                    }},
                    onClick: (event, elements) => {{
                        if (elements.length > 0 && elements[0].element.$context.raw.trade) {{
                            const trade = elements[0].element.$context.raw.trade;
                            showTradeDetails(trade);
                        }}
                    }}
                }}
            }});
        }}
        
        function toggleBTC() {{
            showBTC = !showBTC;
            const btn = document.getElementById('btcToggle');
            if (showBTC) {{
                btn.textContent = '₿ BTC价格: 显示';
                btn.classList.add('active');
            }} else {{
                btn.textContent = '₿ BTC价格: 隐藏';
                btn.classList.remove('active');
            }}
            createChart();
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
                            <div class="info-label">可用现金</div>
                            <div class="info-value">$${{trade.available_cash.toLocaleString()}}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">总收益率</div>
                            <div class="info-value" style="color: ${{trade.return_pct >= 0 ? '#00C853' : '#F44336'}}">
                                ${{trade.return_pct >= 0 ? '+' : ''}}${{trade.return_pct}}%
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">总收益</div>
                            <div class="info-value" style="color: ${{(trade.account_value - 10000) >= 0 ? '#00C853' : '#F44336'}}">
                                ${{(trade.account_value - 10000) >= 0 ? '+' : ''}}$${{Math.abs(trade.account_value - 10000).toFixed(2)}}
                            </div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">夏普比率</div>
                            <div class="info-value">${{trade.sharpe_ratio.toFixed(3)}}</div>
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
                        <button class="show-details-btn" onclick="loadTradeDetails('${{trade.model}}', ${{trade.cycle}})">
                            📋 展示完整交易详情
                        </button>
                        <div class="trade-details-full" id="trade-details-full-${{trade.cycle}}">
                            <!-- Details will be loaded here -->
                        </div>
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
        
        async function loadTradeDetails(modelId, cycleId) {{
            const detailsContainer = document.getElementById(`trade-details-full-${{cycleId}}`);
            
            // Toggle if already loaded
            if (detailsContainer.classList.contains('active')) {{
                detailsContainer.classList.remove('active');
                return;
            }}
            
            // Show loading spinner
            detailsContainer.innerHTML = '<div class="loading-spinner">⏳ 加载详细数据...</div>';
            detailsContainer.classList.add('active');
            
            try {{
                // Load trade data from JSON file
                const response = await fetch(`cleaned_data/${{modelId}}_trades.json`);
                if (!response.ok) {{
                    throw new Error('Failed to load trade data');
                }}
                
                const trades = await response.json();
                const tradeData = trades.find(t => t.cycle_id === cycleId);
                
                if (!tradeData) {{
                    detailsContainer.innerHTML = '<div class="loading-spinner">❌ 未找到对应的交易数据</div>';
                    return;
                }}
                
                // Format and display the detailed trade information
                detailsContainer.innerHTML = formatTradeDetails(tradeData);
                
            }} catch (error) {{
                console.error('Error loading trade details:', error);
                detailsContainer.innerHTML = '<div class="loading-spinner">❌ 加载失败，请检查数据文件</div>';
            }}
        }}
        
        function formatTradeDetails(trade) {{
            // Format account info
            const accountInfo = trade.account_info || {{}};
            const accountHTML = `
                <div class="detail-section">
                    <div class="detail-section-title">📊 账户信息</div>
                    <div class="detail-row">
                        <span class="detail-key">账户价值</span>
                        <span class="detail-value">$${{accountInfo.account_value?.toLocaleString() || 'N/A'}}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">可用现金</span>
                        <span class="detail-value">$${{accountInfo.available_cash?.toLocaleString() || 'N/A'}}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">总收益率</span>
                        <span class="detail-value" style="color: ${{accountInfo.return_pct >= 0 ? '#00C853' : '#F44336'}}">
                            ${{accountInfo.return_pct >= 0 ? '+' : ''}}${{accountInfo.return_pct?.toFixed(2) || 'N/A'}}%
                        </span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">总收益</span>
                        <span class="detail-value" style="color: ${{(accountInfo.account_value - 10000) >= 0 ? '#00C853' : '#F44336'}}">
                            ${{(accountInfo.account_value - 10000) >= 0 ? '+$' : '-$'}}${{Math.abs(accountInfo.account_value - 10000).toFixed(2) || 'N/A'}}
                        </span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">夏普比率</span>
                        <span class="detail-value">${{accountInfo.sharpe_ratio?.toFixed(3) || 'N/A'}}</span>
                    </div>
                </div>
            `;
            
            // Format position changes
            const positionChanges = trade.position_changes || [];
            const positionsHTML = positionChanges.map(change => {{
                const pos = change.position_details || {{}};
                return `
                    <div class="detail-section">
                        <div class="detail-section-title">🔄 ${{change.symbol}} - ${{change.change_type}}</div>
                        <div class="detail-row">
                            <span class="detail-key">数量变化</span>
                            <span class="detail-value">${{change.prev_quantity?.toFixed(2) || '0'}} → ${{change.curr_quantity?.toFixed(2) || '0'}}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">当前价格</span>
                            <span class="detail-value">$${{pos.current_price?.toFixed(2) || 'N/A'}}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">入场价格</span>
                            <span class="detail-value">$${{pos.entry_price?.toFixed(2) || 'N/A'}}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">杠杆倍数</span>
                            <span class="detail-value">${{pos.leverage || 'N/A'}}x</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">名义价值</span>
                            <span class="detail-value">$${{pos.notional_value?.toLocaleString() || 'N/A'}}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">未实现盈亏</span>
                            <span class="detail-value" style="color: ${{pos.unrealized_pnl >= 0 ? '#00C853' : '#F44336'}}">
                                $${{pos.unrealized_pnl >= 0 ? '+' : ''}}${{pos.unrealized_pnl?.toFixed(2) || 'N/A'}} 
                                (${{pos.unrealized_pnl_pct >= 0 ? '+' : ''}}${{pos.unrealized_pnl_pct?.toFixed(2) || 'N/A'}}%)
                            </span>
                        </div>
                    </div>
                `;
            }}).join('');
            
            // Format COT trace
            const cotTrace = trade.cot_trace || 'No COT trace available';
            const cotHTML = `
                <div class="detail-section">
                    <div class="detail-section-title">🧠 完整思考过程 (Chain of Thought)</div>
                    <div class="cot-full-text">${{cotTrace}}</div>
                </div>
            `;
            
            // Format metadata
            const metadataHTML = `
                <div class="detail-section">
                    <div class="detail-section-title">ℹ️ 元数据</div>
                    <div class="detail-row">
                        <span class="detail-key">Cycle ID</span>
                        <span class="detail-value">${{trade.cycle_id || 'N/A'}}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">时间戳</span>
                        <span class="detail-value">${{new Date(trade.timestamp * 1000).toLocaleString('zh-CN')}}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">模型</span>
                        <span class="detail-value">${{trade.model_id || 'N/A'}}</span>
                    </div>
                </div>
            `;
            
            return `
                ${{metadataHTML}}
                ${{accountHTML}}
                ${{positionsHTML}}
                ${{cotHTML}}
            `;
        }}
    </script>
    
    <div class="footer">
        <div class="footer-logo">
            <a href="https://kcores.com" target="_blank">
                <img src="assets/images/kcores-llm-arena-logo-black.png" alt="Kcores LLM Arena">
            </a>
        </div>
        <div class="footer-text">
            Powered by <a href="https://kcores.com" target="_blank" style="color: #007AFF; text-decoration: none;">Kcores LLM Arena</a>
        </div>
        <div class="footer-links">
            <a href="https://x.com/karminski3" target="_blank">@Karminski牙医</a>
            <span style="color: #d2d2d7;">|</span>
            <a href="https://github.com" target="_blank">GitHub</a>
            <span style="color: #d2d2d7;">|</span>
            <a href="https://kcores.com" target="_blank">Kcores.com</a>
        </div>
    </div>
</body>
</html>'''
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"\nHTML visualization with BTC overlay generated: {OUTPUT_HTML}")
    print(f"Total trades: {len(js_trades)}")
    print(f"BTC data points: {len(js_btc['line'])}")
    print(f"\nOpen {OUTPUT_HTML} in your web browser!")


def main():
    """Main execution"""
    print("=" * 60)
    print("GENERATING ENHANCED TRADING TIMELINE")
    print("=" * 60)
    
    # Load data
    all_trades = load_all_trades()
    btc_data = load_btc_data()
    
    print(f"Loaded {len(all_trades)} trades")
    print(f"Loaded {len(btc_data.get('raw_prices', []))} BTC price points")
    
    # Generate HTML
    generate_html(all_trades, btc_data)
    
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()

