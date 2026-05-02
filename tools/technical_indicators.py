#!/usr/bin/env python3
"""
技术指标计算工具 - MA、Bollinger Bands、RSI、Pivot Points
支持从 CSV/JSON 数据或 yfinance 直接计算
"""
import sys
import json
import pandas as pd
import numpy as np


def calc_ma(prices, window):
    """简单移动平均"""
    return prices.rolling(window=window).mean().iloc[-1] if len(prices) >= window else None


def calc_bollinger(prices, window=20, num_std=2):
    """
    布林带 (Bollinger Bands)

    Returns:
        dict: upper, middle, lower
    """
    if len(prices) < window:
        return None

    ma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()

    upper = (ma + std * num_std).iloc[-1]
    middle = ma.iloc[-1]
    lower = (ma - std * num_std).iloc[-1]

    return {
        'upper': round(upper, 2),
        'middle': round(middle, 2),
        'lower': round(lower, 2),
        'bandwidth': round((upper - lower) / middle * 100, 2) if middle else None
    }


def calc_rsi(prices, window=14):
    """
    RSI 相对强弱指标

    Returns:
        float: RSI值 (0-100)
    """
    if len(prices) < window + 1:
        return None

    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None


def calc_pivot_points(high, low, close):
    """
    枢轴点 (Pivot Points) 计算支撑阻力位

    Returns:
        dict: pivot, r1, r2, s1, s2
    """
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)

    return {
        'pivot': round(pivot, 2),
        'r1': round(r1, 2),
        'r2': round(r2, 2),
        's1': round(s1, 2),
        's2': round(s2, 2)
    }


def calc_macd(prices, fast=12, slow=26, signal=9):
    """
    MACD 指标

    Returns:
        dict: macd_line, signal_line, histogram
    """
    if len(prices) < slow:
        return None

    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line

    return {
        'macd': round(macd_line.iloc[-1], 4),
        'signal': round(signal_line.iloc[-1], 4),
        'histogram': round(histogram.iloc[-1], 4),
        'trend': 'bullish' if histogram.iloc[-1] > 0 else 'bearish'
    }


def analyze_all(prices_df):
    """
    综合分析所有技术指标

    Args:
        prices_df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']

    Returns:
        dict: 所有指标结果
    """
    closes = prices_df['close']

    # 获取最近一天的数据用于 pivot points
    recent = prices_df.iloc[-1]
    high = recent['high']
    low = recent['low']
    close = recent['close']

    return {
        'current_price': round(close, 2),
        'ma': {
            'ma5': round(calc_ma(closes, 5), 2) if calc_ma(closes, 5) is not None else None,
            'ma10': round(calc_ma(closes, 10), 2) if calc_ma(closes, 10) is not None else None,
            'ma20': round(calc_ma(closes, 20), 2) if calc_ma(closes, 20) is not None else None,
            'ma60': round(calc_ma(closes, 60), 2) if calc_ma(closes, 60) is not None else None
        },
        'bollinger': calc_bollinger(closes),
        'rsi': calc_rsi(closes),
        'macd': calc_macd(closes),
        'pivot_points': calc_pivot_points(high, low, close)
    }


def fetch_and_analyze(symbol, period='1y', interval='1d'):
    """
    从 yfinance 获取数据并分析

    Args:
        symbol: 股票代码（如 AAPL, 0700.HK）
        period: 时间跨度（1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y）
        interval: K线周期（1d=日线, 1wk=周线, 1mo=月线）
                  - 日线（6.2/6.3 指标）：period=1y,  interval=1d
                  - 周线（6.1 周线趋势）：period=2y,  interval=1wk
                  - 月线（6.1 月线趋势）：period=5y,  interval=1mo

    Returns:
        dict: 分析结果，含 interval 字段便于调用方区分来源
    """
    try:
        import yfinance as yf

        # 港股代码归一化：'00700' / '700' → '0700.HK'
        if symbol.isdigit():
            symbol = str(int(symbol)).zfill(4) + '.HK'

        tk = yf.Ticker(symbol)
        hist = tk.history(period=period, interval=interval)

        if hist.empty:
            return {'error': f'No data found for {symbol}'}

        # 标准化列名
        hist.columns = [c.lower().replace(' ', '_') for c in hist.columns]

        result = analyze_all(hist)
        result['interval'] = interval  # 标注数据粒度，方便调用方区分
        return result

    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  日线（默认）: python technical_indicators.py analyze <symbol> [period]")
        print("  周线:        python technical_indicators.py analyze <symbol> 2y 1wk")
        print("  月线:        python technical_indicators.py analyze <symbol> 5y 1mo")
        print("  从CSV分析:   python technical_indicators.py csv <filepath>")
        print("")
        print("Examples:")
        print("  python technical_indicators.py analyze AAPL 1y")
        print("  python technical_indicators.py analyze 0316.HK 2y 1wk")
        print("  python technical_indicators.py analyze 0316.HK 5y 1mo")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'analyze':
        symbol = sys.argv[2]
        period = sys.argv[3] if len(sys.argv) > 3 else '1y'
        interval = sys.argv[4] if len(sys.argv) > 4 else '1d'
        result = fetch_and_analyze(symbol, period, interval)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == 'csv':
        filepath = sys.argv[2]
        df = pd.read_csv(filepath)
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        result = analyze_all(df)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown command: {cmd}")
