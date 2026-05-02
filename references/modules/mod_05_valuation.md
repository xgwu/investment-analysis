# 模块 5：未来3年估值预测

## 要求清单
- [ ] 5.1 三情景目标价测算（CAGR 来自季度动量，调用 valuation_calculator.py momentum）
- [ ] 5.2 估值方法交叉验证
- [ ] 5.3 敏感性分析矩阵（与5.1交叉验证）

## 计算指令（运行工具）

```bash
# ── 步骤 0：从 Phase 1 已抓取的数据中提取 quarterly_momentum ──
# 读取 quarterly_momentum.revenue_yoy_trend（最新在前，如 [25.0, 30.0, 28.0, 22.0]）
# 读取 quarterly_momentum.suggested_base_cagr / bear / bull

# ── 步骤 1：用季度动量直接推导三情景目标价 ──
python tools/valuation_calculator.py momentum \
    <eps_ttm> <current_price> <target_pe> \
    <yoy_Q0> <yoy_Q-1> <yoy_Q-2> <yoy_Q-3>
# 输出 scenarios.bear/base/bull 即为 5.1 三情景

# ── 步骤 2：生成敏感性矩阵（PE × CAGR）──
python tools/valuation_calculator.py matrix <eps_ttm> <current_price> 3
# CAGR 轴以 suggested_base_cagr 为中心展开

# ── 步骤 3：交叉验证：5.1 目标价必须与 5.3 矩阵对应单元格一致 ──
```

> **CAGR 选取原则**（优先级从高到低）：
> 1. `quarterly_momentum.suggested_*_cagr`（4季度 YoY 均值推导）——**首选**
> 2. 管理层当期业绩指引（财报电话会/2.3节）——若有明确指引则覆盖
> 3. 5年年均 CAGR（`financial_history` 年均增速）——仅作背景参考，不直接用作输入

## 输出格式

### 5.1 三情景假设及目标价测算

> CAGR 锚点来自 `quarterly_momentum.cagr_basis`：_____（填入实际值）

| 情景 | 概率 | CAGR假设（来源） | 目标PE | 目标价 | 预期盈亏 | 触发条件 |
|-----|------|----------------|-------|-------|---------|---------|
| 悲观 | | `suggested_bear_cagr`=__% | | | | |
| 基准 | | `suggested_base_cagr`=__% | | | | |
| 乐观 | | `suggested_bull_cagr`=__% | | | | |

**计算公式展示**：
```
TTM EPS = ___（来自 quarterly_momentum.ttm_net_income / shares_outstanding）
未来EPS = TTM EPS × (1 + CAGR)³ = ___
目标价 = 未来EPS × 目标PE = ___
```

**与5年 CAGR 对比**：5年年均 CAGR = ___%，当前季度动量 CAGR = ___%，
差异说明：（如差异>10pp，必须解释原因）

---

### 5.2 估值方法交叉验证

| 方法 | 估值结果 | 权重 | 备注 |
|-----|---------|------|------|
| PE估值 | | 40% | |
| DCF估值 | | 30% | |
| PB-ROE估值 | | 20% | |
| EV/EBITDA | | 10% | |
| **综合目标价** | | | |

---

### 5.3 估值敏感性分析矩阵

**目标价敏感性（CAGR vs PE）**：

| CAGR \ PE | 15 | 20 | 25 | 30 | 35 |
|----------|----|----|----|----|----|
| 5% | | | | | |
| 10% | | | | | |
| 15% | | | | | |
| 20% | | | | | |
| 25% | | | | | |

**涨幅敏感性（%）**：

| CAGR \ PE | 15 | 20 | 25 | 30 | 35 |
|----------|----|----|----|----|----|
| 5% | | | | | |
| 10% | | | | | |
| 15% | | | | | |
| 20% | | | | | |
| 25% | | | | | |

⚠️ **交叉验证结果**：5.1三情景目标价与5.3矩阵对应单元格一致：✓ / ✗

