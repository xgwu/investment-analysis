# 数据可靠性指南与降级策略

## 数据源可靠性评级

| 数据源 | 实时性 | 稳定性 | 覆盖市场 | 降级优先级 |
|-------|--------|--------|---------|-----------|
| **yfinance** | ★★★★☆ (15min延迟) | ★★★☆☆ (偶有API限制) | 美股/港股/全球 | 首选 |
| **akshare** | ★★★★★ (准实时) | ★★★☆☆ (依赖东财/新浪) | A股/港股/宏观 | A股首选 |
| **新浪财经** | ★★★★★ (实时) | ★★★★☆ (稳定) | A股/港股/美股 | 行情备用 |
| **东方财富** | ★★★★☆ (15min延迟) | ★★★★☆ (稳定) | A股/港股/美股 | 财报备用 |
| **Alpha Vantage** | ★★★☆☆ (延迟) | ★★★★★ (稳定) | 美股 | 美股备用 |
| **网页抓取** | ★★★☆☆ (延迟) | ★★☆☆☆ (易失效) | 全市场 | 最后手段 |

## 多层级降级策略

### 层级 1: 主数据源（实时API）

```python
# 美股/港股首选
yfinance.Ticker(symbol).info
yfinance.Ticker(symbol).history()

# A股首选
ak.stock_zh_a_hist()
ak.stock_financial_abstract_ths()
```

### 层级 2: 备用API（准实时）

```python
# 新浪财经实时行情（A股/港股）
https://hq.sinajs.cn/list=sh600519  # A股
https://hq.sinajs.cn/list=hk00700   # 港股
https://hq.sinajs.cn/list=gb_aapl   # 美股

# 东方财富
ak.stock_zh_a_spot_em()  # A股实时
```

### 层级 3: 网页抓取（延时备份）

```python
# 东方财富网页
https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index

# 雪球
https://stock.finance.sina.com.cn/usstock/quotes/AAPL.html

# Yahoo Finance网页（当API失效）
https://finance.yahoo.com/quote/AAPL
```

### 层级 4: 缓存数据（最终兜底）

```python
# 本地缓存文件
~/.investment-analysis/cache/
├── AAPL_info.json      # 基础信息缓存
├── AAPL_history.csv    # 历史价格缓存
└── AAPL_financials.json # 财报缓存

# 使用场景：所有API都失效时，提示用户数据时效性
```

## 数据质量验证清单

### 实时数据验证

- [ ] 价格是否在合理区间（非0、非负数、非极端值）
- [ ] 市值与股价×股本是否匹配（误差<5%）
- [ ] PE/PB是否为合理数值（非None、非Infinity）
- [ ] 时间戳是否为近期（<24小时）

### 财报数据验证

- [ ] 营收、利润是否为正值（正常经营企业）
- [ ] 毛利率是否在0-100%之间
- [ ] ROE是否在-50%到100%之间
- [ ] 数据时间是否为最近季度

### 技术指标验证

- [ ] MA值是否在价格区间内
- [ ] RSI是否在0-100之间
- [ ] 布林带是否上轨>中轨>下轨

## 数据缺失应对策略

| 缺失类型 | 应对方式 | 标记方式 |
|---------|---------|---------|
| 实时价格 | 使用最近缓存，标记延时 | 「价格数据延时，使用缓存」 |
| 财务指标 | 尝试计算（如用市值/净利润算PE） | 「PE为推算值」 |
| 竞对数据 | 减少竞对数量，至少保留1家 | 「竞对数据部分缺失」 |
| 全部缺失 | 终止分析，提示用户 | 「数据获取失败，请手动提供」 |

## 缓存策略

```python
# 缓存有效期设置
CACHE_TTL = {
    'realtime_price': 300,      # 5分钟
    'daily_history': 3600,      # 1小时
    'financials': 86400,        # 24小时
    'macro': 3600,              # 1小时
}
```
