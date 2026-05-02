# 数据抓取代码参考

## akshare 接口（A股/港股）

```python
import akshare as ak

# === 行情/K线 ===
# A股历史行情（后复权）
df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20200101", adjust="hfq")

# 港股历史行情
df = ak.stock_hk_hist(symbol="00700", period="daily", start_date="20200101", adjust="")

# === 财务报表 ===
# 美股（东方财富）
df = ak.stock_financial_us_report_em(stock="AAPL", symbol="资产负债表", indicator="年报")
df = ak.stock_financial_us_analysis_indicator_em(symbol="AAPL", indicator="年报")

# 港股（东方财富）
df = ak.stock_financial_hk_report_em(stock="00700", symbol="资产负债表", indicator="年度")

# A股（同花顺）
df = ak.stock_financial_abstract_ths(symbol="600519", indicator="按年度")

# === 宏观数据 ===
df = ak.macro_bank_usa_interest_rate()  # 美联储利率
df = ak.bond_zh_us_rate(start_date="20240101")  # 中美利率
```

## yfinance 接口（美股/港股）

```python
import yfinance as yf

# 获取股票对象
tk = yf.Ticker("AAPL")  # 或 "0700.HK"

# === 基础信息 ===
info = tk.info
pe = info.get("forwardPE")
roe = info.get("returnOnEquity", 0) * 100
market_cap = info.get("marketCap")
shares_out = info.get("sharesOutstanding")

# === 财务报表（注意遍历列获取5年数据）===
income_stmt = tk.financials
cashflow = tk.cashflow

# 提取5年数据
for col in income_stmt.columns[:5]:
    year = str(col.year)
    rev = income_stmt.loc["Total Revenue", col]
    net_income = income_stmt.loc["Net Income", col]
    gross_profit = income_stmt.loc["Gross Profit", col]
    # 手动计算比率
    gross_margin = gross_profit / rev if rev else None
    net_margin = net_income / rev if rev else None

# === 历史价格 ===
hist = tk.history(period="5y")  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
```

## 目标价计算模板

```python
def calc_target_price_pe(eps_local, cagr, target_pe, years=3):
    """PE估值法（盈利标的）"""
    future_eps = eps_local * ((1 + cagr) ** years)
    target_price = future_eps * target_pe
    return target_price

def calc_target_price_ps(current_price, shares_out, rev, target_ps, cagr, years=3):
    """PS估值法（未盈利标的）"""
    if not current_price or not rev or not shares_out:
        return None
    future_rev = rev * ((1 + cagr) ** years)
    target_mcap = future_rev * target_ps
    target_price = target_mcap / shares_out
    upside = (target_price - current_price) / current_price
    return target_price, upside * 100

def calc_with_exchange_rate(eps_cny, cny_to_hkd_rate, cagr, target_pe, years=3):
    """港股汇率换算示例：EPS人民币→港币"""
    eps_hkd = eps_cny * cny_to_hkd_rate  # 人民币转港币
    future_eps_hkd = eps_hkd * ((1 + cagr) ** years)
    target_price_hkd = future_eps_hkd * target_pe
    return target_price_hkd
```

## 网页搜索（财报电话会/新闻）

```python
import urllib.request
import urllib.parse
import re

def search_earnings_call(company_name, quarter):
    """搜索最新财报电话会议纪要"""
    query = f"{company_name} {quarter} 电话会议 会议纪要"
    url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    })
    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
    
    snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    results = []
    for s in snippets[:5]:
        clean = re.sub(r'<[^>]+>', '', s).replace('&#39;', "'").replace('&quot;', '"').strip()
        results.append(clean)
    return results
```

## 技术指标计算

```python
import pandas as pd
import numpy as np

def calc_ma(prices, window):
    """简单移动平均"""
    return prices.rolling(window=window).mean()

def calc_bollinger(prices, window=20, num_std=2):
    """布林带"""
    ma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper = ma + (std * num_std)
    lower = ma - (std * num_std)
    return upper, ma, lower

def calc_rsi(prices, window=14):
    """RSI指标"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_pivot_points(high, low, close):
    """枢轴点"""
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)
    return pivot, r1, r2, s1, s2
```

## 市场识别 helper

```python
def identify_market(symbol):
    """识别股票所属市场"""
    symbol = str(symbol).strip()
    
    # A股：6位数字
    if symbol.isdigit() and len(symbol) == 6:
        if symbol.startswith(('6', '5', '9')):
            return 'A股', 'sh'  # 上海
        else:
            return 'A股', 'sz'  # 深圳
    
    # 港股：5位数字或含.HK
    if symbol.endswith('.HK') or (symbol.isdigit() and len(symbol) == 5):
        return '港股', 'hk'
    
    # 美股：字母代码
    if symbol.isalpha():
        return '美股', 'us'
    
    return '未知', 'unknown'
```
