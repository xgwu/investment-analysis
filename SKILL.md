---
name: investment-analysis
description: 通用投资分析框架 V0.1 - 支持A股/港股/美股的深度价值投资分析，含多层数据降级、数据验证、大师三视角
tags: [投资研究, A股, 港股, 美股, 价值投资, 技术分析]
author: Kenny Wu 
version: 0.1.0
license: MIT
---

# 通用投资分析框架 V0.1

> **反幻觉与数据绝对真实性铁律**
> - 绝对禁止使用 LLM 内部训练数据！
> - 所有定量数据必须 100% 来源于真实抓取的 API 或网页文本
> - 数据缺失时必须明确填写「数据缺失，本项跳过」
> - 严禁捏造数据，严禁使用内置过期知识脑补

## 触发条件

当用户要求分析股票/投资标的时，使用此 skill：
- "分析 00700 港股"
- "研究 AAPL 美股"
- "深度研报 600519"
- "投资分析 XXX"

## 数据可靠性策略

### 多层级数据降级

| 层级 | 数据源 | 适用场景 | 状态 |
|-----|--------|---------|------|
| L1a | yfinance / akshare | 美股/A股/港股**实时行情 + 估值倍数** | 首选 |
| L1b | SEC EDGAR XBRL API | 美股**官方年报财务数据**（10-K/20-F，无需 Key） | 与 L1a 并行，覆盖 financial_history |
| L2 | FRED API（免费无需Key） | 美联储利率、US 10Y、CPI 等宏观 | 自动降级（已内置于工具） |
| L3 | WebFetch / WebSearch | 任何 L1/L2 仍缺失的字段 | 流程层手动触发（见下方规则） |
| L4 | 本地缓存 | 全市场 | 兜底 |
| L5 | 用户输入 | - | 最终手段 |

> **SEC EDGAR 说明**：美股分析时 `fetch_us_stock_data()` 自动同时拉取 yfinance（行情）和 SEC EDGAR（财报），合并输出 `source: yfinance+sec_edgar`。中概股 ADR（20-F 申报）的 `gross_profit` 等字段可能因 XBRL 标签不规范而缺失，属已知限制。

### FRED API 覆盖范围（L2，已内置于 data_fetcher_v2.py）

| 字段 | FRED series_id | 触发条件 |
|-----|---------------|---------|
| US 10Y 美债收益率 | `DGS10` | yfinance `^TNX` 返回 None 时自动降级 |
| 美联储基准利率 | `FEDFUNDS` | akshare 接口失败时自动降级 |

### WebFetch / WebSearch 降级规则（L3，Phase 1 手动触发）

**触发条件**：`fetch_macro_data()` 输出中任意字段为 `None` 或空列表 `[]`，且该字段对报告第1节有实质性影响。

**各字段降级目标**：

| 缺失字段 | WebFetch 目标URL | 提取方式 |
|---------|----------------|---------|
| `china_lpr` | `https://www.chinamoney.com.cn/chinese/bkdmgylpr/` | 页面中最新一期 LPR 利率数值 |
| `us_cn_rate`（中美利差） | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10` 与 `https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01CNM156N` | 两者最新值相减 |
| `fed_rate`（若 FRED 也失败） | `https://www.federalreserve.gov/releases/h15/` | 页面中 Federal funds rate 当前区间 |
| 股票相关宏观指标 | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<series>` | 直接 WebFetch CSV 最后一行 |

**执行方式**：
```
# 在 Phase 1 步骤 2 后，若 macro 输出有 None，立即用 WebFetch 补充：
WebFetch(url="...", prompt="提取最新的XXX数据，只需返回数值和日期")
# 将结果手动填入报告 1.2 数据表，标注来源为「WebFetch + 目标网站」
```

**财务数据 WebFetch 降级**（股票 info 字段 None 时）：

| 缺失场景 | 降级来源 | 说明 |
|---------|---------|------|
| 中概股 currentPrice/PE 为 None | `https://finance.yahoo.com/quote/<TICKER>` | WebFetch 抓取 Summary 页数据 |
| 港股财务数据不全 | `https://www.aastocks.com/tc/stocks/analysis/stock-aafn/<CODE>/0/1` | WebFetch 抓取财务摘要 |
| A股实时价格 | `https://hq.sinajs.cn/list=sh<CODE>` | WebFetch 新浪实时行情接口 |

**财报电话会 WebSearch 降级**（2.3节管理层指引字段缺失时）：

> **触发条件**：2.3节中 `管理层指引` 或 `Q&A关键问答` 为"数据缺失"时，立即触发以下搜索。

| 市场 | 搜索词 | 目标数据 |
|------|--------|---------|
| 美股 / 中概ADR | `"<COMPANY>" "<QUARTER> <YEAR>" earnings call transcript` | Seeking Alpha transcript（最全），或 businesswire press release |
| 美股 / 中概ADR | `"<TICKER>" Q&A analyst "<YEAR>" earnings call Chen Lei` | 关键高管名字 + Q&A，过滤出问答摘要 |
| 港股 | `"<公司名>" "<季度>" 业绩发布会 管理层 指引` | 华尔街见闻 / 36kr / 雪球港股频道 |
| A股 | `"<股票代码>" "<季度>" 业绩说明会 管理层 指引` | 同花顺/东方财富互动问答 |

**执行方式**：
```
# 示例：PDD Q4 2025
WebSearch(query='PDD Holdings Q4 2025 earnings call transcript management guidance 2026')
WebSearch(query='PDD Holdings Q4 2025 earnings call Chen Lei key quotes Q&A analyst')

# 提取并填入 2.3 节：
# - 核心战略定调（管理层原话）
# - 指引方向（收入/利润/资本开支）
# - Q&A 3-5个关键问答
# - 超/低预期总结
# 标注来源：「WebSearch，来源：Seeking Alpha / businesswire / 华尔街见闻」
```

---

**行业先导指标 WebSearch 降级**（3.2节数据缺失时）：

> **触发条件**：3.2节任意先导指标字段为"数据缺失"时，按下表分类搜索。

| 指标类型 | 适用标的 | 搜索词 | 来源 |
|---------|---------|--------|------|
| App下载量/MAU | 消费类互联网（电商/社媒/出海） | `"<APP名>" monthly active users "<年份>" Sensor Tower` | Sensor Tower / Similarweb / data.ai |
| 跨境电商流量 | Temu / SHEIN / TikTok Shop 等 | `Temu US monthly active users downloads "<季度>" Sensor Tower Similarweb` | Sensor Tower；注意两者口径差异需在报告标注 |
| 中国社零/消费 | 所有A股/港股/中概 | `中国社会消费品零售总额 "<年份>全年" 国家统计局 同比` | 国家统计局官网；全年值通常1月发布 |
| 消费者信心指数 | 所有中国消费类标的 | `中国消费者信心指数 "<年份>" 国家统计局 最新` | 国家统计局；荣枯线=100，低于则偏弱 |
| 宏观政策/行业监管 | 中国互联网/平台经济 | `国务院 "<行业>" 监管政策 "<年份>"` | 新华社 / 国务院官网 |
| 美国电商市场 | 跨境出海类标的 | `US e-commerce market share "<年份>" eMarketer` | eMarketer / Statista |

**执行方式**：
```
# 示例：Temu 美国市场先导指标
WebSearch(query='Temu monthly active users US 2025 Q4 Sensor Tower Similarweb')
WebSearch(query='中国社会消费品零售总额 2025年全年 国家统计局 同比增速')
WebSearch(query='中国消费者信心指数 2025年 国家统计局 最新')

# 填入 3.2 节时需标注：
# - 数值、来源名称、数据时效（月份）
# - 多来源数据口径差异（如Sensor Tower安卓单平台 vs Similarweb全渠道）
# - 趋势判断：与本标的业务逻辑的正/负相关性
```

### 数据质量验证流程

```bash
# 1. 抓取数据
python tools/data_fetcher_v2.py us AAPL

# 2. 验证数据质量
python tools/data_validator.py price '{抓取的数据JSON}'

# 3. 检查是否有警告/错误
# 如果有 error → 切换到备用数据源
# 如果有 warning → 在报告中标记
```

### 本地执行环境与工具降级注意

- 若系统 `python` 不存在或依赖缺失，优先使用 skill 目录内虚拟环境：`/Users/wuxiaogang/.hermes/skills/research/investment-skill/.venv/bin/python`。该 venv 通常已安装 `yfinance`、`akshare`、`requests`、`pandas`、`numpy`、`pdfminer.six` 等研报工具依赖。
- ⚠️ **venv 可能不存在**（已在实战中复现）：若 `.venv/bin/python` 报 "No such file or directory"，直接用系统 python3 安装缺失依赖：
  ```bash
  pip3 install yfinance akshare requests pandas numpy pdfminer.six --break-system-packages -q
  ```
  一次安装后本 session 全程可用，无需重复尝试 venv 路径。
- `data_validator.py report <symbol> <market>` 内部会通过子进程调用字面量 `python`。若系统无 `python`，运行时把 venv 放入 PATH：
  ```bash
  cd /Users/wuxiaogang/.hermes/skills/research/investment-skill
  PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tools/data_validator.py report 00700 hk
  ```
  若 venv 不存在，则用 `python3 tools/data_validator.py ...` 代替，只要系统 python3 已安装依赖即可正常运行。
- Hermes terminal 对前台命令中的 `&` 可能触发"backgrounding"安全拦截，即使 `&` 出现在 here-doc 文本里（如 `FinTech & Business Services`）。生成长报告时优先用 `write_file` 写入 Python 脚本，再用终端执行脚本，避免在 shell here-doc 中直接塞大段正文。
- ⚠️ **macOS 无 `timeout` 命令**（已复现）：`timeout 30 python3 ...` 会报 "command not found"。替代方案：直接运行命令（大多数分析工具在30秒内完成），或用 `gtimeout`（需 `brew install coreutils`）。`technical_indicators.py analyze` 的周线/月线分析通常在10-20秒内完成，直接运行即可，不必加 timeout。
- ⚠️ **`execute_code` 工具缺少 pandas 等依赖**：execute_code sandbox 与系统 python3 环境隔离，pip3 --break-system-packages 安装的包在 execute_code 中不可用。技术指标计算必须通过 `terminal` 调用 `python3 tools/technical_indicators.py`，不要在 execute_code 中 import。
- ⚠️ write_file 大文件 stall 风险：单次写入完整长报告会 stall（已在腾讯报告中复现）。按批次 A/B/C/D/E 分五次写入，首次建立文件，后续 append；单次上限约 800 行正文。

### WebSearch/WebFetch 失败时的官方文件降级

当 WebSearch/WebFetch 返回 401、额度错误或不可用，但浏览器/终端网络可用时，不要终止分析；改用官方 IR 页面 + `browser`/`curl` 直接抓取文件，并在报告中标注“WebSearch/WebExtract 不可用，改用 browser/curl 官方文件降级”。港股互联网公司常见流程：

1. 用浏览器打开公司 IR 页面，执行 JS 收集 PDF/XLS 链接：
   ```javascript
   Array.from(document.querySelectorAll('a')).map(a => ({text:a.innerText.trim(), href:a.href}))
   ```
2. 用 `curl -L -s -o /tmp/<name>.pdf <url>` 下载 Earnings Release、Earnings Presentation、Annual Report；用 `pdfminer.high_level.extract_text()` 提取文本。
3. 对 Historical Operating Metrics 等 Excel 文件，用 pandas 读取：
   ```python
   import pandas as pd
   xl = pd.ExcelFile('/tmp/operating_metrics.xls')
   df = pd.read_excel('/tmp/operating_metrics.xls', sheet_name=xl.sheet_names[0], header=None)
   ```
4. 电话会 Q&A 若只有 webcast、无稳定 transcript 文本，明确写「Q&A关键问答：数据缺失，本项跳过」，但仍必须提取 Earnings Release 中管理层原话、Business Review/Outlook、分部增速、回购/分红/Capex/FCF。

详见 `references/tencent-official-ir-fallback.md`（腾讯/港股互联网官方 IR 文件降级案例）。
另见 `references/hk-ir-curl-fallback.md`（已验证的 curl + pdfminer 完整流程，含腾讯 FY2025 真实 PDF URL）。
另见 `references/tencent-fy2025-ir-artifacts.md`（2026-05-02 实测：腾讯 FY2025 官方 PDF/XLS URL、curl 抓取命令、关键事实与报告填充注意）。

### 数据缺失应对

| 缺失场景 | 降级策略 | 报告标记 |
|---------|---------|---------|
| 实时价格获取失败 | 使用缓存数据（5分钟内有效） | 「使用缓存价格」 |
| 财报数据缺失 | 尝试yfinance/akshare备用接口 | 「财报数据部分缺失」 |
| 竞对数据缺失 | 至少保留1家主要竞对 | 「竞对分析受限」 |
| 全部数据源失败 | 终止分析，请求用户提供 | 「数据获取失败」 |

## 工具链说明

### 数据抓取工具

| 工具 | 功能 | 使用方式 |
|-----|------|---------|
| `data_fetcher_v2.py` | 多层级数据抓取（含降级） | `python tools/data_fetcher_v2.py [a\|hk\|us\|macro] <symbol>` |
| `market_identifier.py` | 识别市场类型 | `python tools/market_identifier.py <symbol>` |

### 数据验证工具

| 工具 | 功能 | 使用方式 |
|-----|------|---------|
| `data_validator.py` | 验证数据合理性 | `python tools/data_validator.py [price\|financial\|technical] '<json>'` |
| `report_validator.py` | 报告完整性校验 | `python tools/report_validator.py <report_path>` |

### 计算工具

| 工具 | 功能 | 使用方式 |
|-----|------|---------|
| `valuation_calculator.py` | 目标价测算（PE/PS/汇率） | `python tools/valuation_calculator.py [pe\|ps\|fx\|matrix] ...` |
| `technical_indicators.py` | 技术指标计算 | `python tools/technical_indicators.py analyze <symbol>` |

## 模块化报告结构

```
references/modules/
├── mod_00_summary.md       # 投资摘要（Executive Summary）⚠️ 最后写，插入开头
├── mod_01_macro.md         # 全球宏观扫描
├── mod_02_financials.md    # 财报核心数据
├── mod_03_business.md      # 业务与护城河
├── mod_04_comps.md         # 横向竞对分析
├── mod_05_valuation.md     # 估值预测
├── mod_06_technical.md     # 技术分析
├── mod_07_masters.md       # 大师三视角（⚠️ 最易跳步）
├── mod_08_decision.md      # 投资裁决
├── mod_09_risks.md         # 失效清单
└── mod_10_position.md      # 仓位管理
```

## 执行流程

### Phase 1: 数据准备（含降级）

1. **识别市场**：
   ```bash
   python tools/market_identifier.py <symbol>
   ```

2. **执行数据抓取（自动降级）**：
   ```bash
   # 美股
   python tools/data_fetcher_v2.py us AAPL
   
   # A股
   python tools/data_fetcher_v2.py a 600519
   
   # 港股
   python tools/data_fetcher_v2.py hk 00700
   ```

3. **数据质量验证**：
   ```bash
   python tools/data_validator.py price '<json_data>'
   ```
   - 如果有 error → 检查降级数据源
   - 如果有 warning → 记录并在报告中标注

4. **技术指标计算**（三周期，分别运行）：
   ```bash
   # 日线（用于 6.2/6.3 具体指标数值）
   python tools/technical_indicators.py analyze <symbol> 1y 1d

   # 周线（用于 6.1 中期趋势判断）
   python tools/technical_indicators.py analyze <symbol> 2y 1wk

   # 月线（用于 6.1 长期趋势判断）
   python tools/technical_indicators.py analyze <symbol> 5y 1mo
   ```

   **组装 6.1 多周期趋势表**：
   - 月线结果（`interval=1mo`）→ 填入"月线趋势"行：MA20/MA60 方向、RSI、MACD 信号
   - 周线结果（`interval=1wk`）→ 填入"周线趋势"行：同上
   - 日线结果（`interval=1d`）→ 填入 6.2/6.3 具体数值（布林带、枢轴点、52周区间）
   - 三周期 RSI 对比可识别"周线超卖但月线未超卖"等多层级背离信号

5. **季度动量分析（新）**：
   数据抓取完成后，从返回 JSON 中直接读取 `quarterly_momentum` 字段：
   ```
   quarterly_momentum.revenue_yoy_trend    → 填入 2.5 季度趋势表
   quarterly_momentum.avg_revenue_yoy      → base CAGR 锚点
   quarterly_momentum.trend                → accelerating / stable / decelerating
   quarterly_momentum.suggested_*_cagr    → 直接传入下一步估值计算
   quarterly_momentum.ttm_*               → 填入 2.5 TTM 指标
   ```

5a. **财报电话会补全（L3 WebSearch）**：
   数据抓取后，若 2.3 节管理层指引/Q&A 为空，**立即触发** WebSearch 降级（见上方"财报电话会 WebSearch 降级"表）。
   - 搜索目标：管理层原话、2026展望、Q&A 3-5条
   - 标注来源：「WebSearch，来源：Seeking Alpha / businesswire」
   - **不可跳过**：电话会内容是判断管理层意图和短期催化剂的核心依据

5b. **行业先导指标补全（L3 WebSearch）**：
   生成 3.2 节时，若先导指标为"数据缺失"，**立即触发** WebSearch 降级（见上方"行业先导指标 WebSearch 降级"表）。
   - 每个标的至少补全 2 项先导指标（下载量/用户数 或 行业宏观数据）
   - 标注来源和数据口径（Sensor Tower安卓口径 vs Similarweb全渠道）

6. **目标价测算（基于季度动量）**：
   ```bash
   # 首选：用季度 YoY 自动推导三情景
   python tools/valuation_calculator.py momentum \
       <eps_ttm> <current_price> <target_pe> \
       <yoy_Q0> <yoy_Q-1> <yoy_Q-2> <yoy_Q-3>

   # 敏感性矩阵
   python tools/valuation_calculator.py matrix <eps_ttm> <current_price> 3
   ```

### Phase 2: 报告生成（批次策略）

**批次 A（模块 1-4）**：数据模块
- 读取 `mod_01_macro.md` → 生成 → 写入
- 读取 `mod_02_financials.md` → 生成 → 追加
- 读取 `mod_03_business.md` → 生成 → 追加
- 读取 `mod_04_comps.md` → 生成 → 追加

**批次 B（模块 5-6）**：计算密集型
- 读取 `mod_05_valuation.md` → 填入工具计算结果 → 追加
- 读取 `mod_06_technical.md` → 填入工具计算结果 → 追加

**批次 C（模块 7）**：⚠️ **必须独立生成**
- 读取 `mod_07_masters.md` → 生成
- **强制要求**：大师三视角每段≥150字，禁止合并！
- 追加到报告

**批次 D（模块 8-10）**：总结模块
- 读取 `mod_08_decision.md` → 追加
- 读取 `mod_09_risks.md` → 追加
- 读取 `mod_10_position.md` → 追加

**批次 E（模块 0）**：⚠️ **必须最后写，写完后插入报告开头**
- 读取 `mod_00_summary.md` → 提炼全报告 → 生成 Executive Summary
- **插入位置**：报告标题行之后、`## 1. 全球宏观扫描` 之前
- **强制要求**：目标价与 5.1 一致，投资评级与 8.1 一致，核心逻辑3条+风险2条，关键数据速览表8-10项

### Phase 3: 校验与交付

1. **数据一致性校验**：
   ```bash
   python tools/data_validator.py report <symbol> <market>
   ```

2. **报告完整性校验**：
   ```bash
   python tools/report_validator.py /tmp/<TICKER>_report.md
   ```

3. **人工检查重点**：
   - [ ] 7.1/7.2/7.3 是否独立展开（不是合并成一段）
   - [ ] 5.1 与 5.3 的目标价是否一致
   - [ ] 3.0 死穴压测是否≥300字
   - [ ] 数据缺失项是否明确标注「数据缺失」
   - [ ] 降级数据是否标注来源和时效

4. **备份报告**：
   ```bash
   mkdir -p ~/reports && cp /tmp/<TICKER>_report.md ~/reports/
   ```

## 异常处理

| 场景 | 处理方式 |
|-----|---------|
| 未上市/私募公司 | 终止定量模型，转为"一级市场定性商业调研" |
| L1数据源失败 | 自动降级到L2/L3，报告中标注数据来源 |
| 数据验证失败 | 标记「数据存疑」，尝试备用源或请求用户确认 |
| 全部数据源失败 | 终止分析，提示用户提供数据 |
| 净利润为负 | 自动切换 PS 估值模型 |

## 输出格式

报告保存至：`/tmp/<TICKER>_report.md`

结构要求：
- 所有表格使用 Markdown 格式
- 大师三视角必须独立分段（7.1, 7.2, 7.3），禁止合并
- 3.0 业务死穴压测必须≥300字，正负篇幅均衡
- 目标价计算引用工具输出
- **数据降级必须标注**：「数据来源：XXX」「数据时效：延时X小时」
- **数据缺失必须标注**：「数据缺失，本项跳过」

## 参考文档

- `references/data-reliability-guide.md` - 数据可靠性与降级策略详解
- `references/modules/README.md` - 分模块生成说明
- `references/checklist.md` - 交付检查清单
