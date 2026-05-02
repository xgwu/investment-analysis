#!/usr/bin/env python3
"""
估值计算工具 - 目标价测算（PE/PS 模型）
支持汇率换算和敏感性分析矩阵生成
"""
import sys
import json


def calc_target_price_pe(eps, cagr, target_pe, years=3, current_price=None):
    """
    PE估值法（盈利标的）

    Args:
        eps: 当前每股收益（本地货币）
        cagr: 年化增长率（小数，如0.15表示15%）
        target_pe: 目标PE倍数
        years: 预测年数，默认3年
        current_price: 当前股价（用于计算涨幅）

    Returns:
        dict: 包含目标价、涨幅、中间计算值
    """
    future_eps = eps * ((1 + cagr) ** years)
    target_price = future_eps * target_pe

    result = {
        'method': 'PE',
        'eps_current': round(eps, 4),
        'cagr': f"{cagr * 100:.1f}%",
        'years': years,
        'target_pe': target_pe,
        'eps_future': round(future_eps, 4),
        'target_price': round(target_price, 2)
    }

    if current_price:
        upside = (target_price / current_price - 1) * 100
        result['current_price'] = current_price
        result['upside_pct'] = round(upside, 2)

    return result


def calc_target_price_ps(current_price, shares_out, revenue, target_ps, cagr, years=3):
    """
    PS估值法（未盈利标的）

    Args:
        current_price: 当前股价
        shares_out: 总股本
        revenue: 当前营收
        target_ps: 目标PS倍数
        cagr: 年化增长率（小数）
        years: 预测年数

    Returns:
        dict: 计算结果或 None（参数不足时）
    """
    if not all([current_price, shares_out, revenue]):
        return None

    future_revenue = revenue * ((1 + cagr) ** years)
    target_mcap = future_revenue * target_ps
    target_price = target_mcap / shares_out
    upside = (target_price - current_price) / current_price * 100

    return {
        'method': 'PS',
        'revenue_current': round(revenue, 2),
        'cagr': f"{cagr * 100:.1f}%",
        'years': years,
        'target_ps': target_ps,
        'revenue_future': round(future_revenue, 2),
        'target_mcap': round(target_mcap, 2),
        'target_price': round(target_price, 2),
        'current_price': current_price,
        'upside_pct': round(upside, 2)
    }


def calc_with_exchange_rate(eps_foreign, fx_rate, cagr, target_pe, years=3, current_price=None):
    """
    跨市场汇率换算估值（如港股财报EPS人民币转港币）

    Args:
        eps_foreign: 外币计价的EPS（如人民币）
        fx_rate: 汇率（外币兑本地货币，如 1.09 表示 1人民币=1.09港币）
        cagr: 年化增长率
        target_pe: 目标PE
        years: 预测年数
        current_price: 当前股价（本地货币）

    Returns:
        dict: 计算结果
    """
    eps_local = eps_foreign * fx_rate
    result = calc_target_price_pe(eps_local, cagr, target_pe, years, current_price)
    result['eps_foreign'] = round(eps_foreign, 4)
    result['fx_rate'] = fx_rate
    result['eps_local'] = round(eps_local, 4)
    result['note'] = f"汇率换算: {eps_foreign} * {fx_rate} = {eps_local}"

    return result


def generate_sensitivity_matrix(eps, current_price, pe_range, cagr_range, years=3):
    """
    生成估值敏感性分析矩阵

    Args:
        eps: 当前EPS
        current_price: 当前股价
        pe_range: PE范围，如 [10, 15, 20, 25, 30]
        cagr_range: CAGR范围（小数），如 [0.05, 0.10, 0.15, 0.20, 0.25]
        years: 预测年数

    Returns:
        dict: 矩阵数据，包含目标价和涨幅
    """
    matrix = {
        'pe_range': pe_range,
        'cagr_range': [f"{c*100:.0f}%" for c in cagr_range],
        'years': years,
        'target_prices': {},
        'upside_pcts': {}
    }

    for cagr in cagr_range:
        cagr_key = f"{cagr * 100:.0f}%"
        matrix['target_prices'][cagr_key] = {}
        matrix['upside_pcts'][cagr_key] = {}

        for pe in pe_range:
            result = calc_target_price_pe(eps, cagr, pe, years, current_price)
            pe_key = f"PE{pe}"
            matrix['target_prices'][cagr_key][pe_key] = result['target_price']
            matrix['upside_pcts'][cagr_key][pe_key] = result['upside_pct']

    return matrix


def calc_momentum_scenarios(eps, current_price, yoy_list, target_pe, years=3):
    """
    基于季度 YoY 趋势推导三情景目标价。

    Args:
        eps:           当前 EPS（或 TTM EPS）
        current_price: 当前股价
        yoy_list:      最近 N 个季度的营收同比增速（%），如 [25.0, 30.0, 28.0, 22.0]，最新在前
        target_pe:     目标 PE 倍数（三情景共用基础值，悲观/乐观按比例调整）
        years:         预测年数，默认 3

    Returns:
        dict: 三情景计算结果 + CAGR 推导依据
    """
    if not yoy_list:
        return {'error': 'yoy_list 不能为空'}

    avg_yoy = sum(yoy_list) / len(yoy_list)

    # 加速度（最近2季 vs 之前2季均值差）
    if len(yoy_list) >= 4:
        acceleration = sum(yoy_list[:2]) / 2 - sum(yoy_list[2:]) / 2
        trend = 'accelerating' if acceleration > 3 else ('decelerating' if acceleration < -3 else 'stable')
    elif len(yoy_list) >= 2:
        acceleration = yoy_list[0] - yoy_list[-1]
        trend = 'accelerating' if acceleration > 3 else ('decelerating' if acceleration < -3 else 'stable')
    else:
        acceleration = 0.0
        trend = 'insufficient_data'

    base_cagr = avg_yoy / 100
    bear_cagr = base_cagr * 0.65
    bull_cagr = min(base_cagr * 1.35, base_cagr + 0.15)

    # 目标 PE：乐观+20%，悲观-20%
    bear_pe = round(target_pe * 0.80)
    bull_pe = round(target_pe * 1.20)

    scenarios = {}
    for name, cagr, pe in [
        ('bear', bear_cagr, bear_pe),
        ('base', base_cagr, target_pe),
        ('bull', bull_cagr, bull_pe),
    ]:
        res = calc_target_price_pe(eps, cagr, pe, years, current_price)
        scenarios[name] = res

    return {
        'yoy_list':          [round(y, 2) for y in yoy_list],
        'avg_revenue_yoy':   round(avg_yoy, 2),
        'acceleration':      round(acceleration, 2),
        'trend':             trend,
        'bear_cagr':         round(bear_cagr * 100, 2),
        'base_cagr':         round(base_cagr * 100, 2),
        'bull_cagr':         round(bull_cagr * 100, 2),
        'cagr_basis':        f'基于最近{len(yoy_list)}个季度营收同比均值 {avg_yoy:.1f}%（{trend}）',
        'scenarios':         scenarios,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  PE估值:     python valuation_calculator.py pe <eps> <cagr> <target_pe> [current_price] [years]")
        print("  PS估值:     python valuation_calculator.py ps <current_price> <shares_out> <revenue> <target_ps> <cagr> [years]")
        print("  汇率PE:     python valuation_calculator.py fx <eps_foreign> <fx_rate> <cagr> <target_pe> [current_price] [years]")
        print("  敏感性矩阵: python valuation_calculator.py matrix <eps> <current_price> [years] [pe_min] [pe_max]")
        print("  季度动量:   python valuation_calculator.py momentum <eps> <current_price> <target_pe> <yoy1> [yoy2] [yoy3] [yoy4] [years]")
        print("              yoy 为最近各季度营收同比（%），最新在前，如: 25.0 30.0 28.0 22.0")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'pe':
        eps = float(sys.argv[2])
        cagr = float(sys.argv[3])
        target_pe = float(sys.argv[4])
        current_price = float(sys.argv[5]) if len(sys.argv) > 5 else None
        years = int(sys.argv[6]) if len(sys.argv) > 6 else 3
        result = calc_target_price_pe(eps, cagr, target_pe, years, current_price)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == 'ps':
        current_price = float(sys.argv[2])
        shares_out = float(sys.argv[3])
        revenue = float(sys.argv[4])
        target_ps = float(sys.argv[5])
        cagr = float(sys.argv[6])
        years = int(sys.argv[7]) if len(sys.argv) > 7 else 3
        result = calc_target_price_ps(current_price, shares_out, revenue, target_ps, cagr, years)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "Error: Invalid parameters")

    elif cmd == 'fx':
        eps_foreign = float(sys.argv[2])
        fx_rate = float(sys.argv[3])
        cagr = float(sys.argv[4])
        target_pe = float(sys.argv[5])
        current_price = float(sys.argv[6]) if len(sys.argv) > 6 else None
        years = int(sys.argv[7]) if len(sys.argv) > 7 else 3
        result = calc_with_exchange_rate(eps_foreign, fx_rate, cagr, target_pe, years, current_price)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == 'matrix':
        eps = float(sys.argv[2])
        current_price = float(sys.argv[3])
        years = int(sys.argv[4]) if len(sys.argv) > 4 else 3
        # 可选参数：pe_min pe_max，默认自动以 current_price/eps 为中心生成合理范围
        pe_min_arg = float(sys.argv[5]) if len(sys.argv) > 5 else None
        pe_max_arg = float(sys.argv[6]) if len(sys.argv) > 6 else None

        if pe_min_arg is not None and pe_max_arg is not None:
            # 用户指定范围，均匀生成 7 档
            step = max(1, round((pe_max_arg - pe_min_arg) / 6))
            pe_range = sorted(set(
                [round(pe_min_arg + i * step) for i in range(7)] + [round(pe_max_arg)]
            ))
        else:
            # 自动：以当前 PE（current_price/eps）为锚点，向下覆盖 0.5x，向上覆盖 3x
            implied_pe = current_price / eps if eps > 0 else 15
            floor = max(3, round(implied_pe * 0.5 / 5) * 5)  # 向下取整到 5 的倍数
            ceiling = round(implied_pe * 3 / 5) * 5
            step = max(1, round((ceiling - floor) / 6 / 5) * 5) or 5
            pe_range = sorted(set(range(floor, ceiling + step, step)))[:8]

        cagr_range = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
        matrix = generate_sensitivity_matrix(eps, current_price, pe_range, cagr_range, years)
        matrix['pe_range_note'] = f'PE范围 {pe_range[0]}~{pe_range[-1]}（当前隐含PE≈{current_price/eps:.1f}x）' if eps > 0 else ''
        print(json.dumps(matrix, indent=2, ensure_ascii=False))

    elif cmd == 'momentum':
        # momentum <eps> <current_price> <target_pe> <yoy1> [yoy2] [yoy3] [yoy4] [years]
        # yoy 为各季度营收同比（%），最新在前；years 若为整数则作为最后一个参数
        if len(sys.argv) < 5:
            print("Usage: python valuation_calculator.py momentum <eps> <current_price> <target_pe> <yoy1> [yoy2...] [years]")
            sys.exit(1)
        eps          = float(sys.argv[2])
        current_price = float(sys.argv[3])
        target_pe    = float(sys.argv[4])
        # 解析 yoy 列表（可以是 1-4 个浮点数，最后一个整数视为 years）
        raw_args = sys.argv[5:]
        years = 3
        if raw_args and raw_args[-1].isdigit() and len(raw_args) > 1:
            years = int(raw_args[-1])
            raw_args = raw_args[:-1]
        yoy_list = [float(v) for v in raw_args]
        result = calc_momentum_scenarios(eps, current_price, yoy_list, target_pe, years)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown command: {cmd}")
