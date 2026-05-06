# 数据降级规则手册

> 本文件是 SKILL.md 的补充。仅在主数据源（L1/L2）字段缺失时查阅。

---

## L2：FRED API 覆盖字段（已内置于 data_fetcher_v2.py，自动降级）

| 字段 | FRED series_id | 触发条件 |
|------|---------------|---------|
| US 10Y 美债收益率 | `DGS10` | yfinance `^TNX` 返回 None 时 |
| 美联储基准利率 | `FEDFUNDS` | akshare 接口失败时 |

---

## L3：WebFetch 降级目标（宏观字段为 None 时）

| 缺失字段 | URL | 提取内容 |
|---------|-----|---------|
| `china_lpr` | `https://www.chinamoney.com.cn/chinese/bkdmgylpr/` | 最新一期 LPR 数值 |
| `us_cn_rate`（中美利差） | FRED CSV：`fredgraph.csv?id=DGS10` 与 `fredgraph.csv?id=IRLTLT01CNM156N` | 两值相减 |
| `fed_rate`（FRED 也失败时）| `https://www.federalreserve.gov/releases/h15/` | Federal funds rate 当前区间 |

```
WebFetch(url="...", prompt="提取最新的XXX数据，只需返回数值和日期")
# 结果填入报告 1.2，标注来源为「WebFetch + 目标网站」
```

---

## L3：WebFetch 降级目标（股票字段为 None 时）

| 缺失场景 | URL | 说明 |
|---------|-----|------|
| 中概股 currentPrice/PE 为 None | `https://finance.yahoo.com/quote/<TICKER>` | 抓 Summary 页 |
| 港股财务数据不全 | `https://www.aastocks.com/tc/stocks/analysis/stock-aafn/<CODE>/0/1` | 财务摘要 |
| A股实时价格 | `https://hq.sinajs.cn/list=sh<CODE>` | 新浪实时行情 |

---

## L3：WebSearch 降级——财报电话会（2.3 节为空时）

**触发条件**：2.3 节管理层指引或 Q&A 为「数据缺失」时立即触发。

| 市场 | 搜索词模板 | 目标数据 |
|------|-----------|---------|
| 美股 / 中概ADR | `"<COMPANY>" "<QUARTER> <YEAR>" earnings call transcript` | Seeking Alpha transcript |
| 美股 / 中概ADR | `"<TICKER>" Q&A analyst "<YEAR>" earnings call` | Q&A 问答摘要 |
| 港股 | `"<公司名>" "<季度>" 业绩发布会 管理层 指引` | 华尔街见闻 / 36kr / 雪球 |
| A股 | `"<股票代码>" "<季度>" 业绩说明会 管理层 指引` | 同花顺 / 东方财富互动问答 |

填入 2.3 节时标注：核心战略定调（管理层原话）、指引方向、Q&A 3-5 条、超/低预期总结。

---

## L3：WebSearch 降级——行业先导指标（3.2 节为空时）

**触发条件**：3.2 节任意先导指标为「数据缺失」时，按标的类型搜索，至少补全 2 项。

| 指标类型 | 适用标的 | 搜索词模板 | 来源 |
|---------|---------|-----------|------|
| App 下载量 / MAU | 消费互联网 / 出海 | `"<APP名>" monthly active users "<年份>" Sensor Tower` | Sensor Tower / Similarweb |
| 跨境电商流量 | Temu / SHEIN / TikTok Shop | `Temu US monthly active users "<季度>" Sensor Tower Similarweb` | 注意安卓单平台 vs 全渠道口径差异 |
| 中国社零 / 消费 | 所有 A股/港股/中概 | `中国社会消费品零售总额 "<年份>全年" 国家统计局 同比` | 国家统计局（全年值通常1月发布）|
| 消费者信心指数 | 中国消费类标的 | `中国消费者信心指数 "<年份>" 国家统计局 最新` | 荣枯线=100，低于则偏弱 |
| 行业监管政策 | 中国互联网 / 平台经济 | `国务院 "<行业>" 监管政策 "<年份>"` | 新华社 / 国务院官网 |
| 美国电商市场 | 跨境出海类 | `US e-commerce market share "<年份>" eMarketer` | eMarketer / Statista |

---

## L3：官方 IR 文件降级（WebSearch/WebFetch 完全不可用时）

适用于港股互联网公司。详细流程见 `hk-ir-curl-fallback.md`，简要步骤：

1. 浏览器打开公司 IR 页面，执行 JS 收集 PDF/XLS 链接：
   ```javascript
   Array.from(document.querySelectorAll('a')).map(a => ({text:a.innerText.trim(), href:a.href}))
   ```
2. `curl -L -s -o /tmp/<name>.pdf <url>` 下载 Earnings Release；用 `pdfminer.high_level.extract_text()` 提取文本。
3. Excel 文件用 pandas 读取：
   ```python
   import pandas as pd
   df = pd.read_excel('/tmp/file.xls', sheet_name=0, header=None)
   ```
4. 若电话会只有 webcast 无 transcript，写「Q&A关键问答：数据缺失，本项跳过」，但仍须提取 Earnings Release 中管理层原话、分部增速、回购/分红/Capex/FCF。

报告中标注：「WebSearch/WebFetch 不可用，改用 browser/curl 官方文件降级」。

腾讯 FY2025 实测 URL 见 `tencent-fy2025-ir-artifacts.md`。

---

## 数据源可靠性速查

| 数据源 | 实时性 | 稳定性 | 覆盖市场 | 用途 |
|-------|--------|--------|---------|------|
| yfinance | ★★★★☆ 15min延迟 | ★★★☆☆ | 美股/港股/全球 | L1 首选 |
| akshare | ★★★★★ 准实时 | ★★★☆☆ | A股/港股/宏观 | A股首选 |
| FRED API | ★★★☆☆ 日频 | ★★★★★ | 美国宏观 | L2 自动降级 |
| SEC EDGAR XBRL | 季报发布后 | ★★★★★ | 美股官方财报 | L1b，与yfinance并行 |
| WebFetch / WebSearch | 实时 | ★★☆☆☆ 易失效 | 全市场 | L3 手动触发 |

> SEC EDGAR 说明：中概股 ADR（20-F）的 `gross_profit` 等字段因 XBRL 标签不规范可能缺失，属已知限制。
