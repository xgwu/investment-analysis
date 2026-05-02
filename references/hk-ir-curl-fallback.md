# 港股 IR 官方文件 curl 降级方案（WebSearch/WebFetch 401 时）

> 适用场景：WebSearch 和 WebFetch 均返回 401 Unauthorized，但终端网络正常。

## 验证过的腾讯 IR 文件抓取流程（2026-05-02 实测）

### Step 1 — 抓取 PDF 链接列表

```bash
curl -s "https://www.tencent.com/en-us/investors.html" \
  | python3 -c "
import sys, re
data = sys.stdin.read()
links = re.findall(r'href=[\"\'](.*?pdf.*?)[\"\'i]', data, re.I)
[print(l) for l in links[:30]]
"
```

链接规律：`https://static.www.tencent.com/uploads/<YYYY>/<MM>/<DD>/<hash>.pdf`
- 最新年报/季报通常在列表前几条（按上传时间倒序）
- 第1条 = 业绩公告（Earnings Release）
- 第2条 = 业绩演示文稿（Earnings Presentation）

### Step 2 — 下载并提取文本

```bash
curl -s -L -o /tmp/tencent_earnings.pdf "<URL>"
python3 -c "
from pdfminer.high_level import extract_text
txt = extract_text('/tmp/tencent_earnings.pdf')
print(txt[:8000])
"
```

**依赖**：`pip3 install pdfminer.six --break-system-packages -q`

### Step 3 — 定向搜索关键字段

```python
from pdfminer.high_level import extract_text
txt = extract_text('/tmp/tencent_earnings.pdf')

# 管理层指引/展望
idx = txt.find('Outlook')
print(txt[idx:idx+2000])

# Q4 财务亮点
idx = txt.find('4Q2025 Financial Highlights')
print(txt[idx:idx+1500])

# 分业务收入
idx = txt.find('Management Discussion')
print(txt[idx:idx+3000])
```

## FY2025 关键 PDF URL（已验证可用）

| 文件 | URL |
|------|-----|
| FY2025 业绩公告 (Earnings Release) | https://static.www.tencent.com/uploads/2026/03/18/e6a646796d0d869acc76271c9ee1a6a5.pdf |
| FY2025 业绩演示文稿 (Presentation) | https://static.www.tencent.com/uploads/2026/03/18/2804dbdae364ca25b82d21bc8304f1d3.pdf |
| Q3 2025 业绩公告 | https://static.www.tencent.com/uploads/2025/11/13/（需从IR页面重新抓取） |

## 注意事项

- IR 页面 JS 渲染不影响 `curl` 抓取，因为 PDF 链接已静态嵌入 HTML
- 业绩电话会 transcript 无稳定 PDF，只有 webcast；管理层指引从 Earnings Release 的 "Business Review and Outlook" 节提取
- Q&A 部分若无 transcript 则标记「数据缺失，本项跳过」，但 Earnings Release 中的 CEO 原话必须提取
- 若 Python `requests.get()` 下载 `static.www.tencent.com` 偶发 `ProxyError: Tunnel connection failed: 408 Request Time-out`，不要卡住；改用 `curl -L --retry 3 --connect-timeout 20 -o /tmp/<file> <url>`，本流程已在腾讯 FY2025 PDF/XLS 上验证。
- 腾讯 IR 的 `Historical Operating Metrics` 是 XLS 文件，可用 `pandas.ExcelFile` + `pd.read_excel(..., header=None)` 读取；关键字段包括微信/WeChat MAU、QQ MAU、VAS订阅、员工数。
