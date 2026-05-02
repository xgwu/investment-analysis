# 腾讯 FY2025 官方 IR 抓取与关键事实（2026-05-02 实测）

用途：港股互联网公司分析时，WebSearch/WebExtract 401 或额度不可用，改用 browser/curl 官方 IR 文件降级。本文件记录腾讯 FY2025 可复用 URL、抓取命令、关键字段位置与注意事项。

## 官方 IR 页面

- 页面：https://www.tencent.com/en-us/investors.html
- browser 控制台收集链接：

```javascript
Array.from(document.querySelectorAll('a'))
  .map(a => ({text:a.innerText.trim(), href:a.href}))
  .filter(x => /Historical|Operating|xls|xlsx|Earnings|Annual Report|Presentation|Release/i.test(x.text+x.href))
```

## 已验证文件 URL

| 文件 | URL | 用途 |
|---|---|---|
| FY2025 Earnings Release | https://static.www.tencent.com/uploads/2026/03/18/e6a646796d0d869acc76271c9ee1a6a5.pdf | 收入、利润、分部、Business Review and Outlook、回购/FCF |
| FY2025 Earnings Presentation | https://static.www.tencent.com/uploads/2026/03/18/2804dbdae364ca25b82d21bc8304f1d3.pdf | 4Q/FY表格、策略页、Q&A占位、回购分红页 |
| 2025 Annual Report | https://static.www.tencent.com/uploads/2026/04/09/62d786fcf3d3c8cb7e54791ee95439ac.pdf | 年报全文 |
| Historical Operating Metrics XLS | https://static.www.tencent.com/uploads/2026/03/18/b3b13dc53205e8fa0b8bbca880188a6d.xls | 微信/WeChat MAU、QQ MAU、VAS订阅、员工数 |

## 抓取命令

优先用 `curl`，不要只依赖 Python `requests`：本次 requests 下载 static.www.tencent.com 文件偶发 `ProxyError: Tunnel connection failed: 408 Request Time-out`，但 `curl -L --retry 3 --connect-timeout 20` 成功。

```bash
curl -L --retry 3 --connect-timeout 20 -o /tmp/tencent_earnings_release.pdf 'https://static.www.tencent.com/uploads/2026/03/18/e6a646796d0d869acc76271c9ee1a6a5.pdf'
curl -L --retry 3 --connect-timeout 20 -o /tmp/tencent_presentation.pdf 'https://static.www.tencent.com/uploads/2026/03/18/2804dbdae364ca25b82d21bc8304f1d3.pdf'
curl -L --retry 3 --connect-timeout 20 -o /tmp/tencent_operating_metrics.xls 'https://static.www.tencent.com/uploads/2026/03/18/b3b13dc53205e8fa0b8bbca880188a6d.xls'
```

PDF 文本提取：

```python
from pdfminer.high_level import extract_text
for name in ['earnings_release','presentation']:
    txt = extract_text(f'/tmp/tencent_{name}.pdf')
    open(f'/tmp/tencent_{name}.txt','w').write(txt)
```

XLS 读取：

```python
import pandas as pd
path='/tmp/tencent_operating_metrics.xls'
xl=pd.ExcelFile(path)
df=pd.read_excel(path, sheet_name=xl.sheet_names[0], header=None)
print(df.head(40).to_string(max_cols=14, max_rows=40))
```

## FY2025 关键事实（官方文件）

- FY2025收入 RMB751.8bn，同比 +14%。
- FY2025毛利 RMB422.6bn，同比 +21%。
- FY2025 Non-IFRS经营利润 RMB280.7bn，同比 +18%，经营利润率37%。
- FY2025 Non-IFRS归母净利 RMB259.6bn，同比 +17%。
- FY2025 IFRS归母净利 RMB224.8bn，同比 +16%。
- FY2025 Capex RMB79.2bn，同比 +3%。
- FY2025 Free cash flow RMB182.6bn，同比 +18%；净现金 RMB107.1bn。
- FY2025回购约153.4m股，金额约HKD80.0bn。
- FY2025拟年度分红 HKD5.30/股，合计约HKD48bn。
- Presentation注明：因AI投资机会高，未来回购金额可能低于2025，同时提高股息。
- 2025国内游戏收入 RMB164.2bn，同比 +18%。
- 2025国际游戏收入 RMB77.4bn，同比 +33%，全年超过USD10bn。
- 2025Marketing Services收入 RMB145.0bn，同比 +19%。
- 2025FinTech and Business Services收入 RMB229.4bn，同比 +8%。
- 4Q2025收入 RMB194.4bn，同比 +13%，环比 +0.8%。
- 4Q2025Marketing Services收入 RMB41.1bn，同比 +17%，环比 +13%。
- 微信/WeChat合并MAU 1,418m（2025Q4），同比 +2%，环比 +0.3%。
- QQ移动端MAU 508m（2025Q4），同比 -3%，环比 -2%。
- VAS订阅 267m（2025Q4），同比 +2%，环比 +0.8%。
- Video Accounts total user time spent 同比增长超过20%。
- Mini Shops、Mini Games和内容相关Mini Programs用户参与同比快速增长。

## 报告填充注意

- 2.3 电话会 Q&A：官方页面有Webcast Replay，但未提供稳定transcript文本时，写「Q&A关键问答：数据缺失，本项跳过」；不要用LLM记忆补Q&A。
- 3.2 行业先导指标：优先使用官方运营指标（微信MAU、视频号时长、小程序互动、国际游戏收入）作为内部先导指标；外部行业总量若无法抓取，明确标注数据缺失。
- 估值：若用Non-IFRS EPS人民币换港币，CNY/HKD可由 `USD/HKD ÷ USD/CNY` 计算，并把汇率与公式写进5.1。
