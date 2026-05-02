# 分模块报告生成说明

为降低 LLM 跳步风险，将原 `report-template.md` 拆分为 10 个独立模块。

## 使用方法

### 方式 1：逐模块生成（推荐，零跳步）

每个模块独立生成，完成后追加到报告文件：

```bash
# 初始化报告
echo "# 投资分析报告：\`TICKER\`" > /tmp/TICKER_report.md

# 逐模块生成（每个模块单独调用LLM）
# 每次只读取一个 mod_XX_xxx.md 文件作为上下文

for module in mod_01_macro.md mod_02_financials.md mod_03_business.md ...; do
    # 1. 读取当前模块模板
    # 2. 读取已生成的报告内容（用于上下文连贯）
    # 3. 生成当前模块内容
    # 4. 追加写入报告文件
done
```

### 方式 2：批次生成（平衡效率与质量）

将模块按数据依赖关系分组：

- **批次 A（模块 1-4）**：纯数据模块，可并行预计算
  - mod_01_macro（宏观数据）
  - mod_02_financials（财报数据）
  - mod_03_business（业务分析）
  - mod_04_comps（竞对数据）

- **批次 B（模块 5-6）**：计算密集型，需工具输出
  - mod_05_valuation（估值测算）← 依赖 valuation_calculator.py
  - mod_06_technical（技术分析）← 依赖 technical_indicators.py

- **批次 C（模块 7）**：定性深度分析，最耗电
  - mod_07_masters（大师三视角）← 必须独立处理，禁止合并

- **批次 D（模块 8-10）**：总结性模块
  - mod_08_decision（投资裁决）
  - mod_09_risks（失效清单）
  - mod_10_position（仓位管理）

### 方式 3：全量生成（仅用于简单标的）

对于数据简单、模块少的标的，仍可加载完整模板一次性生成。

## 模块依赖关系

```
mod_01_macro ─────┐
mod_02_financials ─┤
mod_03_business ───┼──→ mod_05_valuation ───┐
mod_04_comps ──────┤                        ├──→ mod_08_decision
mod_06_technical ──┘                        │
mod_07_masters ─────────────────────────────┘
mod_09_risks ───────→ mod_10_position
```

## 防跳步检查清单

每个模块文件头部都有 `[ ]` 格式的要求清单，生成后应逐项勾选确认。

## 文件命名规则

```
mod_{序号:02d}_{模块简称}.md
```

例如：
- `mod_01_macro.md` - 全球宏观扫描
- `mod_07_masters.md` - 大师三视角辩论
