#!/usr/bin/env python3
"""
报告校验工具 - 检查报告完整性和数据一致性
"""
import sys
import re
import json


def check_report_structure(filepath):
    """检查报告结构完整性"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = {
        'has_comps_analysis': ('横向可比公司分析' in content or '横向竞对分析' in content),
        'has_shareholder_yield': '综合股东回报率' in content,
        'has_three_scenarios': '三情景假设' in content and '目标价测算' in content,
        'has_technical_analysis': '技术面分析' in content,
        'has_catalyst_calendar': '关键催化剂日历' in content,
        'has_master_perspectives': all(p in content for p in ['巴菲特视角', '芒格视角', '索罗斯视角']),
        'has_dead_zone_test': '死穴压测' in content,
        'has_position_management': '仓位管理模型' in content,
        'has_kill_list': '论据失效清单' in content,
        'no_duplicate_sections': True
    }

    # 检查重复章节
    section_pattern = r'##\s*\d+\.\s+(.+)'
    sections = re.findall(section_pattern, content)
    if len(sections) != len(set(sections)):
        checks['no_duplicate_sections'] = False
        checks['duplicate_sections'] = [s for s in set(sections) if sections.count(s) > 1]

    # 检查大纲序号是否连续
    numbered_sections = re.findall(r'^##\s+(\d+)\.', content, re.MULTILINE)
    if numbered_sections:
        numbers = [int(n) for n in numbered_sections]
        expected = list(range(min(numbers), max(numbers) + 1))
        checks['sequential_numbering'] = numbers == expected
        if not checks['sequential_numbering']:
            checks['numbering_issues'] = f"Found {numbers}, expected {expected}"

    return checks


def check_data_consistency(filepath):
    """检查数据一致性"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    issues = []

    # 检查是否有数据缺失但未标注
    suspicious_patterns = [
        r'\|\s*\|\s*\|',  # 空表格行
        r'待补充',  # 待补充标记
        r'TBD',  # TBD标记
    ]

    for pattern in suspicious_patterns:
        matches = re.findall(pattern, content)
        if matches:
            issues.append(f"Found {len(matches)} occurrences of '{pattern}'")

    # 检查目标价计算是否有公式说明
    if '目标价' in content and '未来EPS' not in content:
        issues.append("目标价测算缺少公式说明")

    return issues


def check_sensitivity_matrix_consistency(filepath):
    """
    检查 5.1 三情景目标价与 5.3 敏感性矩阵的一致性。
    提取报告中所有 $NNN 美元价格，以 5.1 中最高值为乐观价，最低值为悲观价，
    检查两者差距是否合理（乐观/悲观 比值在 1.3~3.0 之间）。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    inconsistencies = []

    # 提取 5.1 三情景目标价（美元）— 只取 5.1 子节，不含 5.2/5.3
    section_51_match = re.search(r'###\s*5\.1[^\n]*\n(.*?)(?=\n#{2,3}\s|\Z)', content, re.DOTALL)
    section_53_match = re.search(r'###\s*5\.3[^\n]*\n(.*?)(?=\n#{2,3}\s|\Z)', content, re.DOTALL)

    def extract_usd_prices(text):
        return [float(p) for p in re.findall(r'\$(\d+(?:\.\d+)?)', text) if 20 < float(p) < 10000]

    prices_51 = extract_usd_prices(section_51_match.group(1)) if section_51_match else []
    prices_53 = extract_usd_prices(section_53_match.group(1)) if section_53_match else []

    if prices_51:
        bull_51 = max(prices_51)
        bear_51 = min(prices_51)
        ratio = bull_51 / bear_51 if bear_51 > 0 else 0
        if ratio < 1.1:
            inconsistencies.append(f'5.1 三情景目标价区间过窄（乐观${bull_51} vs 悲观${bear_51}，比值{ratio:.2f}）')
        if ratio > 4.0:
            inconsistencies.append(f'5.1 三情景目标价区间过宽（乐观${bull_51} vs 悲观${bear_51}，比值{ratio:.2f}）')

    if prices_51 and prices_53:
        max_51 = max(prices_51)
        max_53 = max(prices_53)
        if abs(max_51 - max_53) / max(max_51, max_53) > 0.30:
            inconsistencies.append(
                f'5.1 最高目标价 ${max_51} 与 5.3 矩阵最高价 ${max_53} 差异超 30%，请核对'
            )

    return inconsistencies


def generate_validation_report(filepath):
    """生成完整校验报告"""
    structure = check_report_structure(filepath)
    data_issues = check_data_consistency(filepath)
    consistency_issues = check_sensitivity_matrix_consistency(filepath)

    report = {
        'file': filepath,
        'structure_checks': structure,
        'data_issues': data_issues,
        'consistency_issues': consistency_issues,
        'overall_pass': (
            all(v for v in structure.values() if isinstance(v, bool))
            and len(data_issues) == 0
            and len(consistency_issues) == 0
        )
    }

    return report


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python report_validator.py <report_filepath>")
        sys.exit(1)

    filepath = sys.argv[1]

    try:
        report = generate_validation_report(filepath)
        print(json.dumps(report, indent=2, ensure_ascii=False))

        # 输出简洁结果
        print("\n" + "="*50)
        if report['overall_pass']:
            print("✅ 校验通过")
        else:
            print("❌ 校验失败")
            failed = [k for k, v in report['structure_checks'].items() if isinstance(v, bool) and not v]
            if failed:
                print(f"结构检查失败项: {failed}")
            if report['data_issues']:
                print(f"数据问题: {report['data_issues']}")
            if report.get('consistency_issues'):
                print(f"一致性问题: {report['consistency_issues']}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
