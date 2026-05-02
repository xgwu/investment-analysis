#!/usr/bin/env python3
"""
市场识别工具 - 根据股票代码判断所属市场
"""
import sys


def identify_market(symbol):
    """识别股票所属市场"""
    symbol = str(symbol).strip().upper()

    # A股：6位数字
    if symbol.isdigit() and len(symbol) == 6:
        if symbol.startswith(('6', '5', '9')):
            return 'A股', 'sh', symbol
        else:
            return 'A股', 'sz', symbol

    # 港股：5位数字
    if symbol.isdigit() and len(symbol) == 5:
        return '港股', 'hk', symbol

    # 港股：含.HK后缀
    if symbol.endswith('.HK'):
        return '港股', 'hk', symbol.replace('.HK', '')

    # 美股：字母代码（可能含特殊后缀如 .O .NS）
    if symbol.replace('.', '').replace('-', '').isalpha():
        return '美股', 'us', symbol

    return '未知', 'unknown', symbol


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python market_identifier.py <symbol>")
        sys.exit(1)

    symbol = sys.argv[1]
    market, exchange, clean_symbol = identify_market(symbol)
    print(f"{market}|{exchange}|{clean_symbol}")
