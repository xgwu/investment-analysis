# 执行环境配置与已知 Workaround

## Python 环境

**优先顺序**：skill 内 venv → 系统 python3（pip3 安装依赖）

```bash
# skill venv（若存在）
/Users/wuxiaogang/.hermes/skills/research/investment-skill/.venv/bin/python

# venv 不存在时，直接用系统 python3 安装依赖（一次即可）
pip3 install yfinance akshare requests pandas numpy pdfminer.six --break-system-packages -q
```

`data_validator.py report` 内部通过子进程调用字面量 `python`，若系统无 `python`：
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tools/data_validator.py report 00700 hk
# 或 venv 不存在时：
python3 tools/data_validator.py report 00700 hk
```

## 已知 Bug / 平台限制

| 问题 | 平台 | 解决方案 |
|------|------|---------|
| `timeout` 命令不存在 | macOS | 直接运行（工具通常 <30s），或 `brew install coreutils` 用 `gtimeout` |
| `&` 触发 backgrounding 拦截 | Hermes terminal | 用 `Write` 工具写 Python 脚本再执行，不要在 here-doc 里内嵌大段正文 |
| `execute_code` 缺少 pandas 等依赖 | 所有平台 | 技术指标计算必须通过 Bash 调 `python3 tools/technical_indicators.py`，不在 execute_code 中 import |
| 单次写入大文件 stall | Claude Code | 分批次写入（A/B/C/D/E），单次上限约 800 行；首次建文件，后续 append |

## 当前环境（WSL2 / Linux）

本 skill 在 WSL2 (Linux) 下运行，无上述 macOS 限制。`timeout` 命令可用，`&` 无拦截问题。
