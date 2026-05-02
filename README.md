# Investment Analysis Skill

通用投资分析框架 V0.1：面向 A 股、港股、美股的深度价值投资研究 skill。它将数据抓取、数据降级、估值计算、技术指标、报告模板和交付校验整合成一套可复用流程，目标是生成“可溯源、可复核、可交付”的投资分析报告。

> 免责声明：本项目仅用于研究、学习与自动化报告生成示例，不构成任何证券投资建议。市场有风险，投资需独立判断。

## 核心原则

本 skill 的第一原则是反幻觉和数据真实性：

- 禁止用 LLM 内部记忆或过期训练数据填充定量事实。
- 所有定量数据必须来自实时抓取的 API、网页文本、官方文件或明确的计算过程。
- 数据缺失时必须显式写明：`数据缺失，本项跳过`。
- WebSearch/WebFetch 不可用时，不终止分析；按降级策略改用官方 IR、curl、PDF/XLS 解析等方式补全。
- 估值、技术指标、报告结构必须经过工具校验或人工 checklist 复核。

## 能做什么

- 自动识别股票市场：A 股 / 港股 / 美股。
- 抓取行情、估值倍数、财务报表、宏观数据和历史价格。
- 对关键数据执行质量验证。
- 计算三周期技术指标：日线、周线、月线。
- 进行 PE / PS / 汇率换算 / 敏感性矩阵估值。
- 生成模块化深度投资报告。
- 强制输出大师三视角：巴菲特、芒格、索罗斯。
- 生成投资裁决、风险失效清单和仓位管理模型。
- 支持官方 IR 文件降级抓取，尤其适合港股互联网公司。

## 适用场景

用户可以用类似下面的请求触发：

```text
分析 00700 港股
研究 AAPL 美股
深度研报 600519
投资分析 腾讯
帮我做一份 PDD 投资分析报告
```

适合：

- 长线价值投资研究
- 财报更新后的复盘
- 标的初筛与横向对比
- 买入前的风险压测
- 估值区间和仓位纪律设计

不适合：

- 高频交易信号
- 无数据来源的主观荐股
- 未上市公司精确估值
- 需要付费数据授权的实时机构级行情

## 支持市场与数据来源

| 市场 | 示例 | 主要数据来源 |
| --- | --- | --- |
| A 股 | `600519` | akshare、公开网页、宏观数据接口 |
| 港股 | `00700` / `0700.HK` | yfinance、akshare、公司 IR、PDF/XLS 文件 |
| 美股 | `AAPL` / `PDD` | yfinance、SEC EDGAR XBRL、FRED、公司公告 |
| 宏观 | 利率、汇率、VIX | yfinance、akshare、FRED、官方网页降级 |

### 数据降级层级

| 层级 | 数据源 | 用途 |
| --- | --- | --- |
| L1a | yfinance / akshare | 行情、估值倍数、历史价格、基础财务 |
| L1b | SEC EDGAR XBRL | 美股官方年报财务数据 |
| L2 | FRED | 美债收益率、联邦基金利率等宏观指标 |
| L3 | WebSearch / WebFetch / 官方网页 | 缺失字段、电话会、行业先导指标 |
| L4 | 本地缓存 | 临时兜底 |
| L5 | 用户输入 | 全部自动来源失败后的最终手段 |

## 项目结构

```text
investment-analysis/
├── SKILL.md                         # Hermes skill 主说明与执行流程
├── README.md                        # GitHub 项目说明
├── tools/
│   ├── market_identifier.py         # 市场识别
│   ├── data_fetcher_v2.py           # 多市场数据抓取与降级
│   ├── data_validator.py            # 行情/财务/技术/报告数据验证
│   ├── valuation_calculator.py      # PE、PS、FX、矩阵估值计算
│   ├── technical_indicators.py      # MA、RSI、MACD、Boll、关键价位
│   └── report_validator.py          # 报告结构完整性校验
└── references/
    ├── report-template.md           # 完整报告模板
    ├── checklist.md                 # 交付前检查清单
    ├── data-sources.md              # 数据抓取代码参考
    ├── data-reliability-guide.md    # 数据可靠性与降级策略
    ├── hk-ir-curl-fallback.md       # 港股 IR curl/PDF 降级案例
    └── modules/
        ├── mod_00_summary.md        # 投资摘要
        ├── mod_01_macro.md          # 全球宏观扫描
        ├── mod_02_financials.md     # 财报核心数据
        ├── mod_03_business.md       # 业务与护城河
        ├── mod_04_comps.md          # 横向竞对分析
        ├── mod_05_valuation.md      # 估值预测
        ├── mod_06_technical.md      # 技术分析
        ├── mod_07_masters.md        # 大师三视角
        ├── mod_08_decision.md       # 投资裁决
        ├── mod_09_risks.md          # 失效清单
        └── mod_10_position.md       # 仓位管理
```

## 快速开始

### 1. 安装依赖

建议使用 Python 3.10+。

```bash
pip3 install yfinance akshare requests pandas numpy pdfminer.six -q
```

如果你的 Python 环境受系统保护，可以按需使用：

```bash
pip3 install yfinance akshare requests pandas numpy pdfminer.six --break-system-packages -q
```

### 2. 识别市场

```bash
python3 tools/market_identifier.py 00700
python3 tools/market_identifier.py AAPL
python3 tools/market_identifier.py 600519
```

### 3. 抓取数据

```bash
# 港股
python3 tools/data_fetcher_v2.py hk 00700

# 美股
python3 tools/data_fetcher_v2.py us AAPL

# A股
python3 tools/data_fetcher_v2.py a 600519

# 宏观
python3 tools/data_fetcher_v2.py macro
```

### 4. 计算技术指标

```bash
# 日线：用于具体指标和关键价位
python3 tools/technical_indicators.py analyze 00700 1y 1d

# 周线：用于中期趋势
python3 tools/technical_indicators.py analyze 00700 2y 1wk

# 月线：用于长期趋势
python3 tools/technical_indicators.py analyze 00700 5y 1mo
```

### 5. 估值计算

```bash
# PE / PS / FX / matrix 等模式，具体参数见工具帮助或 SKILL.md
python3 tools/valuation_calculator.py matrix <eps_ttm> <current_price> 3
```

### 6. 校验报告

```bash
python3 tools/report_validator.py /tmp/<TICKER>_report.md
python3 tools/data_validator.py report <symbol> <market>
```

## 标准工作流

### Phase 1：数据准备

1. 用 `market_identifier.py` 识别市场。
2. 用 `data_fetcher_v2.py` 抓取行情、财务、宏观数据。
3. 用 `data_validator.py` 校验价格和财务数据。
4. 用 `technical_indicators.py` 分别计算日线、周线、月线指标。
5. 若电话会、管理层指引或行业先导指标缺失，执行 WebSearch/WebFetch 或官方文件降级。
6. 用 `valuation_calculator.py` 生成三情景估值和敏感性矩阵。

### Phase 2：报告生成

按模块批次生成，避免长报告一次性写入失败：

| 批次 | 模块 | 内容 |
| --- | --- | --- |
| A | 1-4 | 宏观、财报、业务、竞对 |
| B | 5-6 | 估值、技术分析 |
| C | 7 | 大师三视角，必须独立展开 |
| D | 8-10 | 投资裁决、风险、仓位 |
| E | 0 | Executive Summary，最后生成并插入开头 |

### Phase 3：校验与交付

- 运行数据一致性校验。
- 运行报告结构校验。
- 检查大师三视角是否完整。
- 检查目标价、敏感性矩阵是否一致。
- 检查所有数据缺失项是否显式标注。
- 备份报告到 `~/reports/`。

## 报告结构

生成的报告通常包含以下章节：

1. Executive Summary / 投资摘要
2. 数据质量声明
3. 全球宏观扫描
4. 财报核心数据追踪
5. 业务基本面与护城河
6. 横向可比公司分析
7. 未来 3 年估值预测
8. 技术面分析与关键价位
9. 大师三视角辩论
10. 综合投资裁决
11. 论据失效清单
12. 仓位管理模型

## 关键设计亮点

### 1. 数据真实性优先

任何缺失数据都不会被“合理脑补”。报告中宁可出现 `数据缺失，本项跳过`，也不允许虚构数值。

### 2. 多源降级

同一字段优先 API 抓取；API 不可用时降级到官方网页、PDF、XLS、CSV；仍不可用才标注缺失。

### 3. 定量和定性结合

报告同时覆盖：

- 宏观流动性
- 财务质量
- 业务护城河
- 竞对估值
- 三情景目标价
- 技术面择时
- 大师视角辩论
- 风险失效条件
- 仓位纪律

### 4. 强制校验

`report_validator.py` 和 `references/checklist.md` 用于防止漏掉关键章节，尤其是大师三视角、死穴压测、目标价交叉验证和风险清单。

## 官方 IR 文件降级示例

当 WebSearch/WebFetch 失败，但公司官网可访问时，可以采用以下流程：

```bash
# 下载官方 PDF
curl -L -s -o /tmp/company_earnings.pdf "<official-ir-pdf-url>"

# 提取文本
python3 - <<'PY'
from pdfminer.high_level import extract_text
text = extract_text('/tmp/company_earnings.pdf')
print(text[:5000])
PY
```

对于 Historical Operating Metrics 等 Excel 文件：

```python
import pandas as pd

xl = pd.ExcelFile('/tmp/operating_metrics.xls')
df = pd.read_excel('/tmp/operating_metrics.xls', sheet_name=xl.sheet_names[0], header=None)
print(df.head())
```

## 常见问题

### 为什么报告里会出现“数据缺失，本项跳过”？

这是刻意设计。它表示当前可验证数据源未能提供该字段，系统拒绝使用模型记忆或猜测补数。

### 为什么需要同时做基本面和技术面？

基本面回答“值不值得买”，技术面回答“是否适合现在买”。对于港股、美股这类波动较大的市场，择时和仓位纪律有助于降低追高风险。

### 为什么要有大师三视角？

巴菲特视角强调生意质量与现金流，芒格视角强调反向思考和失败模式，索罗斯视角强调市场情绪与反身性。三者可以帮助避免单一框架偏误。

### WebSearch 不可用怎么办？

按 SKILL.md 中的降级策略处理：优先抓官方 IR 页面、PDF、XLS、SEC、FRED、交易所公告等公开文件；仍不可得时标注数据缺失。

## 开发与维护建议

- 新增数据源时，优先写入 `tools/data_fetcher_v2.py`，并在 `references/data-reliability-guide.md` 中说明降级规则。
- 新增报告章节时，同步更新 `references/report-template.md`、`references/modules/` 和 `tools/report_validator.py`。
- 新增估值模型时，补充 `valuation_calculator.py` 并在 README 中给出最小示例。
- 每次工具逻辑变化后，用真实标的至少跑一遍 A 股、港股或美股样例。

## 交付物约定

默认报告路径：

```text
/tmp/<TICKER>_report.md
```

默认备份路径：

```text
~/reports/<TICKER>_report.md
```

如果需要导入飞书、Notion、GitHub 或其他文档系统，建议先生成 Markdown，再按目标平台优化标题层级、目录、表格和引用块。

## License

MIT
