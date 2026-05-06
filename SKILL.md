---
name: investment-analysis
description: 通用投资分析框架 - 支持A股/港股/美股的深度价值投资分析，含多层数据降级、数据验证、大师三视角
tags: [投资研究, A股, 港股, 美股, 价值投资, 技术分析]
author: Kenny Wu
version: 0.2.0
license: MIT
---

# 通用投资分析框架

> **反幻觉铁律（每次必读）**
> - 绝对禁止使用 LLM 内部训练数据
> - 所有定量数据必须来自真实抓取的 API 或网页
> - 数据缺失时写「数据缺失，本项跳过」，严禁脑补

## 触发条件

当用户要求分析股票/投资标的时使用此 skill：`分析 00700`、`研究 AAPL`、`深度研报 600519`

---

## 数据层级（L1 优先，逐级降级）

| 层级 | 数据源 | 说明 |
|------|--------|------|
| L1a | yfinance / akshare | 行情 + 估值，首选 |
| L1b | SEC EDGAR XBRL | 美股官方财报，与 L1a 并行 |
| L2 | FRED API | 宏观数据，已内置于 data_fetcher_v2.py，自动降级 |
| L3 | WebFetch / WebSearch | L1/L2 字段仍缺时手动触发，见 `references/data-fallback-rules.md` |
| L4 | 本地缓存 | 兜底 |

> 字段缺失时的具体 URL / 搜索词模板，见 **`references/data-fallback-rules.md`**。
> 环境安装问题（venv / macOS timeout / write_file stall），见 **`references/env-setup.md`**。

---

## 工具链

| 工具 | 用途 | 命令 |
|------|------|------|
| `market_identifier.py` | 识别市场 | `python3 tools/market_identifier.py <symbol>` |
| `data_fetcher_v2.py` | 抓取数据（含自动降级）| `python3 tools/data_fetcher_v2.py [a\|hk\|us\|macro] <symbol>` |
| `technical_indicators.py` | 技术指标 | `python3 tools/technical_indicators.py analyze <symbol> <period> <interval>` |
| `valuation_calculator.py` | 目标价测算 | `python3 tools/valuation_calculator.py [momentum\|matrix\|pe\|ps] ...` |
| `data_validator.py` | 数据合理性校验 | `python3 tools/data_validator.py [price\|financial\|technical] '<json>'` |
| `report_validator.py` | 报告完整性校验 | `python3 tools/report_validator.py /tmp/<TICKER>_report.md` |

---

## 报告模块结构

```
references/modules/
├── mod_00_summary.md    ⚠️ 最后写，插入报告开头
├── mod_01_macro.md      全球宏观扫描
├── mod_02_financials.md 财报核心数据
├── mod_03_business.md   业务与护城河
├── mod_04_comps.md      横向竞对分析
├── mod_05_valuation.md  估值预测
├── mod_06_technical.md  技术分析
├── mod_07_masters.md    大师三视角 ⚠️ 最易跳步
├── mod_08_decision.md   投资裁决
├── mod_09_risks.md      失效清单
└── mod_10_position.md   仓位管理
```

---

## Phase 1：数据准备

```bash
# 1. 识别市场
python3 tools/market_identifier.py <symbol>

# 2. 抓取数据（股票 + 宏观并行）
python3 tools/data_fetcher_v2.py [a|hk|us] <symbol>
python3 tools/data_fetcher_v2.py macro

# 3. 若宏观/股票字段为 None → 查 references/data-fallback-rules.md 按市场降级

# 4. 技术指标（三周期）
python3 tools/technical_indicators.py analyze <symbol> 1y  1d   # 日线 → 6.2/6.3
python3 tools/technical_indicators.py analyze <symbol> 2y  1wk  # 周线 → 6.1 中期趋势
python3 tools/technical_indicators.py analyze <symbol> 5y  1mo  # 月线 → 6.1 长期趋势

# 5. 从抓取 JSON 读取 quarterly_momentum 字段 → 填入 2.5，作为估值 CAGR 锚点

# 6. 目标价测算
python3 tools/valuation_calculator.py momentum <eps_ttm> <price> <pe> <Q0> <Q-1> <Q-2> <Q-3>
python3 tools/valuation_calculator.py matrix   <eps_ttm> <price> 3
```

**L3 补全触发点**（若仍缺失，查 `references/data-fallback-rules.md`）：
- 2.3 节管理层指引/Q&A 为空 → WebSearch 财报电话会
- 3.2 节先导指标为空 → WebSearch 行业数据（至少补全 2 项）

---

## Phase 2：报告生成（分批写入，防 stall）

| 批次 | 模块 | 说明 |
|------|------|------|
| A | mod_01 → mod_04 | 数据模块，依次读模板 → 生成 → 追加 |
| B | mod_05 → mod_06 | 计算密集型，填入工具输出 |
| C | mod_07 | ⚠️ 大师三视角**必须独立生成**，每段 ≥150 字，禁止合并 |
| D | mod_08 → mod_10 | 总结模块 |
| E | mod_00 | ⚠️ 最后生成 Executive Summary，**插入报告标题行之后** |

---

## Phase 3：校验与交付

```bash
python3 tools/report_validator.py /tmp/<TICKER>_report.md
mkdir -p ~/reports && cp /tmp/<TICKER>_report.md ~/reports/
```

人工核查：
- [ ] 7.1/7.2/7.3 独立展开，未合并
- [ ] 5.1 目标价与 5.3 矩阵对应单元格一致
- [ ] 3.0 死穴压测 ≥300 字，正负篇幅均衡
- [ ] 数据缺失项标注「数据缺失，本项跳过」

---

## 异常处理

| 场景 | 处理方式 |
|------|---------|
| 未上市 / 私募公司 | 终止定量模型，转「一级市场定性调研」 |
| L1 失败 | 自动降级到 L2/L3，报告标注来源 |
| 数据验证失败 | 标记「数据存疑」，尝试备用源 |
| 全部数据源失败 | 终止分析，提示用户提供数据 |
| 净利润为负 | 自动切换 PS 估值模型 |

---

## 输出规范

- 报告路径：`/tmp/<TICKER>_report.md`
- 所有表格用 Markdown 格式
- 降级数据标注：「数据来源：XXX　时效：延时 X 小时」
- 数据缺失标注：「数据缺失，本项跳过」

---

## 参考文档

| 文件 | 用途 |
|------|------|
| `references/data-fallback-rules.md` | L3 降级 URL / 搜索词 / curl 流程 |
| `references/env-setup.md` | Python 环境、平台 workaround |
| `references/modules/` | 各模块报告模板 |
| `references/checklist.md` | 交付检查清单 |
