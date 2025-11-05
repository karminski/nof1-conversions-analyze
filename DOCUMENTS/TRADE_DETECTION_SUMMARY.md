# 交易判定分析总结

**分析日期**: 2025-11-05  
**数据样本**: 30个文件，3000条对话记录，6个模型  
**检测到的交易**: 120个

---

## 核心发现

### 1. 交易判定的明确标志 ✅

通过对3000条采样数据的分析，我们确认了**最可靠的交易判定方法**：

**主要判定标准**: 
- 比对 `user_prompt` 中的持仓（positions）数量变化
- 这是**最可靠、最准确**的交易发生标志

### 2. 数据结构分析

#### 关键字段及其作用：

| 字段 | 作用 | 用于交易判定 |
|------|------|-------------|
| `user_prompt` | 包含实际持仓信息 | ✅ **主要依据** |
| `llm_response` | 大模型的决策意图 | ⚠️ 辅助参考 |
| `signal` | 交易信号(buy/sell/hold等) | ⚠️ 显示意图，非实际执行 |
| `cot_trace` | 完整思考过程 | 📝 用于分析决策逻辑 |
| `cot_trace_summary` | 思考摘要 | 📝 用于快速理解 |
| `cycle_id` | 交易周期ID | 🔑 关键索引 |
| `timestamp` | 时间戳 | 🔑 时序排序 |

#### Signal字段分布：

- `hold`: 12,458次 (占绝大多数，说明大部分时间在观望)
- `buy_to_enter`: 13次
- `close_position`: 10次  
- `sell_to_enter`: 8次

**关键洞察**: Signal字段**大部分时间是hold**，即使实际持仓在变化。这证实了**不能仅依赖signal字段判断交易**。

### 3. 交易类型分布

从120个检测到的交易中：

| 交易类型 | 数量 | 说明 |
|---------|------|------|
| 减仓 (reduce_position) | 58 | 部分平仓 |
| 加仓 (add_position) | 56 | 增加现有仓位 |
| 反转 (flip_position) | 43 | 多空方向反转 |
| 开仓 (open_position) | 36 | 新开仓位 |
| 平仓 (close_position) | 36 | 完全平仓 |

### 4. 各模型交易频率

| 模型 | 采样记录数 | 交易次数 | 交易频率 |
|------|-----------|---------|---------|
| gemini-2.5-pro | 519 | 40 | 7.7% |
| gpt-5 | 446 | 28 | 6.3% |
| claude-sonnet-4-5 | 507 | 16 | 3.2% |
| deepseek-chat-v3.1 | 424 | 13 | 3.1% |
| grok-4 | 431 | 13 | 3.0% |
| qwen3-max | 673 | 10 | 1.5% |

**洞察**: 
- gemini和gpt-5交易频率最高（可能与其亏损表现相关）
- qwen3-max交易频率最低（盈利冠军，长期持仓策略）

---

## 最终交易判定规则

### 核心算法

```python
def detect_trade(prev_record, curr_record):
    """
    判断两条连续记录之间是否发生了交易
    
    Returns:
        bool: 是否发生交易
        list: 交易变化详情
    """
    # 1. 提取持仓信息（从user_prompt）
    prev_positions = extract_positions_from_prompt(prev_record['user_prompt'])
    curr_positions = extract_positions_from_prompt(curr_record['user_prompt'])
    
    # 2. 转换为字典格式 {symbol: quantity}
    prev_pos_dict = {p['symbol']: p['quantity'] for p in prev_positions}
    curr_pos_dict = {p['symbol']: p['quantity'] for p in curr_positions}
    
    # 3. 检测变化
    all_symbols = set(prev_pos_dict.keys()) | set(curr_pos_dict.keys())
    changes = []
    
    for symbol in all_symbols:
        prev_qty = prev_pos_dict.get(symbol, 0)
        curr_qty = curr_pos_dict.get(symbol, 0)
        
        # 容忍0.01的浮点误差
        if abs(curr_qty - prev_qty) > 0.01:
            changes.append({
                'symbol': symbol,
                'prev_qty': prev_qty,
                'curr_qty': curr_qty,
                'change_type': classify_change(prev_qty, curr_qty)
            })
    
    return len(changes) > 0, changes


def classify_change(prev_qty, curr_qty):
    """分类交易类型"""
    if prev_qty == 0 and curr_qty != 0:
        return 'open_position'
    elif prev_qty != 0 and curr_qty == 0:
        return 'close_position'
    elif (prev_qty > 0 and curr_qty < 0) or (prev_qty < 0 and curr_qty > 0):
        return 'flip_position'
    elif abs(curr_qty) > abs(prev_qty):
        return 'add_position'
    else:
        return 'reduce_position'
```

### 提取持仓信息的正则表达式

```python
def extract_positions_from_prompt(user_prompt: str):
    """从user_prompt中提取持仓信息"""
    positions = []
    
    # 匹配格式: {'symbol': 'SOL', 'quantity': 37.02, ...}
    pattern = r"\{'symbol':\s*'(\w+)',\s*'quantity':\s*([-\d.]+),"
    
    for match in re.finditer(pattern, user_prompt):
        symbol = match.group(1)
        quantity = float(match.group(2))
        positions.append({
            'symbol': symbol,
            'quantity': quantity
        })
    
    return positions
```

---

## 数据清洗策略

基于以上分析，下一步数据清洗应该：

### 1. 处理流程

1. **按模型分组**: 遍历所有56,146个文件，按`model_id`分组
2. **时序排序**: 每个模型的记录按`timestamp`排序
3. **连续比对**: 比对相邻记录的持仓变化
4. **筛选交易记录**: 只保留发生交易的记录

### 2. 保留的数据字段

对于每条交易记录，保留：

- **基础信息**: `timestamp`, `cycle_id`, `model_id`
- **持仓信息**: 从`user_prompt`提取的完整持仓列表
- **交易决策**: `llm_response`（各币种的signal和quantity）
- **思考过程**: `cot_trace`（完整）和`cot_trace_summary`（摘要）
- **账户指标**: 
  - Account Value
  - Total Return %
  - Available Cash
  - Sharpe Ratio
- **交易变化**: 
  - 变化类型（开仓/平仓/加仓/减仓/反转）
  - 前后持仓对比

### 3. 输出格式

建议使用以下两种格式：

#### 方案A: 每个模型一个JSON文件
```
cleaned_data/
  ├── qwen3-max_trades.json
  ├── deepseek-chat-v3.1_trades.json
  ├── gpt-5_trades.json
  ├── claude-sonnet-4-5_trades.json
  ├── gemini-2.5-pro_trades.json
  └── grok-4_trades.json
```

#### 方案B: 统一JSON + CSV索引
```
cleaned_data/
  ├── all_trades.json          # 所有交易的完整数据
  ├── trades_index.csv         # 交易索引（快速查询）
  └── model_summary.json       # 各模型交易统计
```

### 4. 预期结果

- **原始数据**: 56,146个文件，83GB，大量冗余
- **清洗后数据**: 
  - 估计 ~1,000-2,000 条真实交易记录
  - 数据量约 50-100MB
  - **数据压缩比**: ~99.9%

---

## 实例展示

### 交易案例：Claude开仓SOL

**Cycle 680 → 681**

**持仓变化**:
- SOL: 0.00 → 37.02 (开仓)

**Signal变化**:
- SOL: buy_to_enter → hold

**策略思考**:
> My current account is down 13.71% to $8,628.74, with $4,630.18 in cash. I'm holding onto my SOL (small loss), XRP (profitable), and DOGE (small profit) positions...

**关键点**: 
- Signal从`buy_to_enter`变为`hold`，说明已执行买入
- 实际持仓从0变为37.02，确认交易执行

---

## 下一步行动

### ✅ 已完成
1. 数据结构探索
2. 交易判定标志识别
3. 采样验证（3000条记录）
4. 确定核心算法

### 📋 待执行
1. 编写全量数据清洗脚本
2. 处理全部56,146个文件
3. 生成清洗后的数据集
4. 生成清洗报告和统计
5. 验证数据完整性

### 🎯 目标
创建高质量、无冗余的交易数据集，用于后续的：
- 交易策略分析
- 模型决策模式研究
- 盈亏归因分析
- 时间周期偏好分析

---

## 技术要点

### 处理大规模数据的注意事项

1. **内存管理**: 不要一次性加载所有文件，使用流式处理
2. **进度监控**: 每处理1000个文件输出一次进度
3. **错误处理**: 记录无法解析的文件，继续处理
4. **去重策略**: 按(model_id, cycle_id)去重
5. **数据校验**: 确保提取的持仓信息完整准确

### 性能优化

- 使用多进程并行处理（如果系统支持）
- 预编译正则表达式
- 使用生成器而非列表存储大数据
- 定期释放内存

---

## 结论

✅ **交易判定方法已明确**: 通过user_prompt中持仓数量变化判断

✅ **核心算法已验证**: 在3000条采样数据中成功检测120个交易

✅ **数据结构已清晰**: 知道需要保留哪些字段

✅ **准备就绪**: 可以开始全量数据清洗

**推荐**: 立即开始开发全量数据清洗脚本，预计可将83GB数据压缩至50-100MB高质量交易数据集。

