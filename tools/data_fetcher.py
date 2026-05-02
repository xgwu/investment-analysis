#!/usr/bin/env python3
"""
数据抓取工具 - 统一封装 akshare 和 yfinance 接口
支持 A股、港股、美股的多维数据获取
"""
import sys
import json
import pandas as pd


def fetch_a_stock_data(symbol):
    """获取 A股数据"""
    try:
        import akshare as ak

        # 历史行情（后复权）
        hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20190101", adjust="hfq")

        # 财务摘要
        financials = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按年度")

        # 实时行情
        realtime = ak.stock_zh_a_spot_em()
        stock_info = realtime[realtime['代码'] == symbol].to_dict('records')

        return {
            'market': 'A股',
            'symbol': symbol,
            'history': hist.tail(252).to_dict('records') if not hist.empty else [],
            'financials': financials.to_dict('records') if not financials.empty else [],
            'realtime': stock_info[0] if stock_info else {}
        }

    except Exception as e:
        return {'error': str(e), 'market': 'A股', 'symbol': symbol}


def fetch_hk_stock_data(symbol):
    """获取港股数据"""
    try:
        import akshare as ak
        import yfinance as yf

        # 确保符号格式正确
        clean_symbol = symbol.replace('.HK', '')
        yf_symbol = f"{int(clean_symbol):04d}.HK" if clean_symbol.isdigit() else symbol

        # akshare 历史行情
        hist_ak = ak.stock_hk_hist(symbol=clean_symbol, period="daily", start_date="20190101", adjust="")

        # yfinance 补充财务数据
        tk = yf.Ticker(yf_symbol)
        info = tk.info
        financials = tk.financials

        return {
            'market': '港股',
            'symbol': symbol,
            'yf_symbol': yf_symbol,
            'history': hist_ak.tail(252).to_dict('records') if not hist_ak.empty else [],
            'info': {
                'name': info.get('longName'),
                'sector': info.get('sector'),
                'market_cap': info.get('marketCap'),
                'pe': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb': info.get('priceToBook'),
                'roe': info.get('returnOnEquity')
            },
            'financials': financials.to_dict() if not financials.empty else {}
        }

    except Exception as e:
        return {'error': str(e), 'market': '港股', 'symbol': symbol}


def fetch_us_stock_data(symbol):
    """获取美股数据"""
    try:
        import yfinance as yf

        tk = yf.Ticker(symbol)

        # 历史数据
        hist = tk.history(period="5y")

        # 财务报表（遍历获取5年数据）
        income = tk.financials
        balance = tk.balance_sheet
        cashflow = tk.cashflow

        # 提取5年关键指标
        financial_history = []
        if not income.empty:
            for col in income.columns[:5]:
                year_data = {'year': str(col.year)}
                try:
                    year_data['revenue'] = float(income.loc['Total Revenue', col]) if 'Total Revenue' in income.index else None
                    year_data['net_income'] = float(income.loc['Net Income', col]) if 'Net Income' in income.index else None
                    year_data['gross_profit'] = float(income.loc['Gross Profit', col]) if 'Gross Profit' in income.index else None

                    if year_data['revenue'] and year_data['gross_profit']:
                        year_data['gross_margin'] = round(year_data['gross_profit'] / year_data['revenue'] * 100, 2)
                    if year_data['revenue'] and year_data['net_income']:
                        year_data['net_margin'] = round(year_data['net_income'] / year_data['revenue'] * 100, 2)
                except:
                    pass
                financial_history.append(year_data)

        info = tk.info

        return {
            'market': '美股',
            'symbol': symbol,
            'history': hist.tail(252).to_dict('records') if not hist.empty else [],
            'info': {
                'name': info.get('longName'),
                'sector': info.get('sector'),
                'market_cap': info.get('marketCap'),
                'shares_outstanding': info.get('sharesOutstanding'),
                'eps': info.get('trailingEps'),
                'pe': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb': info.get('priceToBook'),
                'ps': info.get('priceToSalesTrailing12Months'),
                'roe': info.get('returnOnEquity'),
                'revenue_growth': info.get('revenueGrowth'),
                'profit_margins': info.get('profitMargins'),
                'current_price': info.get('currentPrice'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow')
            },
            'financial_history': financial_history
        }

    except Exception as e:
        return {'error': str(e), 'market': '美股', 'symbol': symbol}


def fetch_macro_data():
    """获取宏观数据"""
    try:
        import akshare as ak

        # 美联储利率
        fed_rate = ak.macro_bank_usa_interest_rate()

        # 中美利率
        us_cn_rate = ak.bond_zh_us_rate(start_date="20240101")

        return {
            'fed_rate': fed_rate.tail(5).to_dict('records') if not fed_rate.empty else [],
            'us_cn_rate': us_cn_rate.tail(5).to_dict('records') if not us_cn_rate.empty else []
        }

    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  A股: python data_fetcher.py a <symbol>  (如: 600519)")
        print("  港股: python data_fetcher.py hk <symbol> (如: 00700 或 0700.HK)")
        print("  美股: python data_fetcher.py us <symbol> (如: AAPL)")
        print("  宏观: python data_fetcher.py macro")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'a' and len(sys.argv) > 2:
        result = fetch_a_stock_data(sys.argv[2])
    elif cmd == 'hk' and len(sys.argv) > 2:
        result = fetch_hk_stock_data(sys.argv[2])
    elif cmd == 'us' and len(sys.argv) > 2:
        result = fetch_us_stock_data(sys.argv[2])
    elif cmd == 'macro':
        result = fetch_macro_data()
    else:
        print(f"Invalid command: {cmd}")
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
