#!/usr/bin/env python3
"""
数据质量验证工具 - 验证抓取数据的合理性和完整性
"""
import sys
import json
from datetime import datetime, timedelta


def _flatten_fetcher_output(data):
    """
    将 data_fetcher_v2 的嵌套输出拆解为扁平结构。
    输入形如 {"source": ..., "info": {"current_price": ..., "pe": ...}}，
    输出合并后的扁平 dict，info 字段优先（保留 source/market/symbol 供参考）。
    """
    if 'info' in data and isinstance(data['info'], dict):
        flat = {k: v for k, v in data.items() if k != 'info'}
        flat.update(data['info'])
        return flat
    return data


def validate_price_data(data):
    """验证价格数据合理性"""
    errors = []
    warnings = []

    if not data:
        return {'valid': False, 'errors': ['数据为空'], 'warnings': []}

    # 兼容 data_fetcher_v2 的嵌套输出（info 键）
    data = _flatten_fetcher_output(data)

    # 检查必要字段
    required_fields = ['current_price', 'market_cap']
    for field in required_fields:
        if field not in data or data[field] is None:
            errors.append(f'缺少字段: {field}')

    # 验证价格在合理区间
    if 'current_price' in data and data['current_price'] is not None:
        price = data['current_price']
        if price <= 0:
            errors.append(f'价格异常: {price} (应为正数)')
        elif price > 100000:  # 美股BRK.A可能很高
            warnings.append(f'价格极高: {price}，请确认单位')

    # 验证市值与价格匹配
    if all(k in data and data[k] for k in ['market_cap', 'current_price', 'shares_outstanding']):
        calculated_cap = data['current_price'] * data['shares_outstanding']
        actual_cap = data['market_cap']
        if actual_cap > 0:
            diff_pct = abs(calculated_cap - actual_cap) / actual_cap * 100
            if diff_pct > 10:
                warnings.append(f'市值与价格×股本不匹配，差异{diff_pct:.1f}%')

    # 验证估值指标合理性
    for metric, (min_val, max_val) in [
        ('pe', (0.1, 1000)),
        ('pb', (0.1, 100)),
        ('roe', (-0.5, 1.0))
    ]:
        if metric in data and data[metric] is not None:
            val = data[metric]
            if val < min_val or val > max_val:
                warnings.append(f'{metric}异常: {val} (合理范围: {min_val}-{max_val})')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


def validate_financial_data(data):
    """验证财报数据合理性"""
    errors = []
    warnings = []

    if not data or 'financial_history' not in data:
        return {'valid': False, 'errors': ['财报数据缺失'], 'warnings': []}

    history = data.get('financial_history', [])
    if len(history) < 3:
        warnings.append(f'历史数据不足，仅{len(history)}年')

    for year_data in history:
        # 验证营收为正
        if 'revenue' in year_data and year_data['revenue'] is not None:
            if year_data['revenue'] < 0:
                errors.append(f"{year_data.get('year', '未知年份')}营收为负")

        # 验证利润率在合理范围
        for margin_key in ['gross_margin', 'net_margin']:
            if margin_key in year_data and year_data[margin_key] is not None:
                margin = year_data[margin_key]
                if margin < -100 or margin > 100:
                    warnings.append(f"{year_data.get('year', '')}{margin_key}异常: {margin}%")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


def validate_technical_data(data):
    """验证技术指标合理性"""
    errors = []
    warnings = []

    if not data:
        return {'valid': False, 'errors': ['技术指标数据缺失'], 'warnings': []}

    # 验证MA值
    if 'ma' in data:
        ma = data['ma']
        current = data.get('current_price')
        if current and ma.get('ma5'):
            # MA5应该接近当前价
            diff = abs(ma['ma5'] - current) / current
            if diff > 0.5:  # 差异超过50%
                warnings.append(f'MA5与当前价差异过大: {diff*100:.1f}%')

    # 验证RSI
    if 'rsi' in data and data['rsi'] is not None:
        rsi = data['rsi']
        if rsi < 0 or rsi > 100:
            errors.append(f'RSI超出范围: {rsi} (应为0-100)')

    # 验证布林带
    if 'bollinger' in data and data['bollinger']:
        boll = data['bollinger']
        if boll['upper'] < boll['middle'] or boll['middle'] < boll['lower']:
            errors.append('布林带顺序错误: 上轨应>中轨>下轨')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


def generate_data_quality_report(symbol, market):
    """生成完整的数据质量报告（尝试从 data_fetcher_v2 实时抓取）"""
    import subprocess, json as _json

    checks = {
        'price_data': {'status': 'unknown'},
        'financial_data': {'status': 'unknown'},
        'technical_data': {'status': 'unknown'}
    }
    recommendations = []

    try:
        import os
        fetcher = os.path.join(os.path.dirname(__file__), 'data_fetcher_v2.py')
        result = subprocess.run(
            ['python', fetcher, market, symbol],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            raw = _json.loads(result.stdout)
            price_result = validate_price_data(raw)
            checks['price_data'] = {
                'status': 'error' if price_result['errors'] else ('warning' if price_result['warnings'] else 'ok'),
                'errors': price_result['errors'],
                'warnings': price_result['warnings']
            }
            fin_result = validate_financial_data(raw)
            checks['financial_data'] = {
                'status': 'error' if fin_result['errors'] else ('warning' if fin_result['warnings'] else 'ok'),
                'errors': fin_result['errors'],
                'warnings': fin_result['warnings']
            }
            if checks['price_data']['status'] == 'error':
                recommendations.append('价格数据异常，建议切换至 L3 WebFetch 降级源')
            if checks['financial_data']['status'] == 'error':
                recommendations.append('财务数据异常，建议验证 yfinance 接口可用性')
        else:
            for k in checks:
                checks[k] = {'status': 'error', 'errors': [f'data_fetcher_v2 返回错误: {result.stderr[:200]}']}
            recommendations.append('数据抓取失败，请检查网络或切换数据源')
    except Exception as e:
        for k in checks:
            checks[k] = {'status': 'error', 'errors': [str(e)]}
        recommendations.append(f'报告生成异常: {e}')

    all_statuses = [v['status'] for v in checks.values()]
    overall = 'error' if 'error' in all_statuses else ('warning' if 'warning' in all_statuses else 'ok')

    return {
        'symbol': symbol,
        'market': market,
        'timestamp': datetime.now().isoformat(),
        'checks': checks,
        'overall': overall,
        'recommendations': recommendations
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python data_validator.py price '{json_data}'")
        print("  python data_validator.py financial '{json_data}'")
        print("  python data_validator.py technical '{json_data}'")
        print("  python data_validator.py report <symbol> <market>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd in ['price', 'financial', 'technical'] and len(sys.argv) > 2:
        data = json.loads(sys.argv[2])
        validators = {
            'price': validate_price_data,
            'financial': validate_financial_data,
            'technical': validate_technical_data
        }
        result = validators[cmd](data)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == 'report' and len(sys.argv) > 3:
        symbol = sys.argv[2]
        market = sys.argv[3]
        report = generate_data_quality_report(symbol, market)
        print(json.dumps(report, indent=2, ensure_ascii=False))

    else:
        print(f"Invalid arguments: {sys.argv}")
        sys.exit(1)
