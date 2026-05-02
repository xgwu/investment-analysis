#!/usr/bin/env python3
"""
数据抓取工具 V2 - 支持多层级降级和缓存
统一封装 akshare、yfinance、新浪财经等数据源
"""
import sys
import json
import os
import time
from datetime import datetime, timedelta
from functools import wraps

try:
    import pandas as pd
except ImportError:
    pd = None

# 缓存配置
CACHE_DIR = os.path.expanduser('~/.investment-analysis/cache')
CACHE_TTL = {
    'realtime': 300,      # 5分钟
    'history': 3600,      # 1小时
    'financials': 86400,  # 24小时
}


def ensure_cache_dir():
    """确保缓存目录存在"""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(symbol, data_type):
    """获取缓存文件路径"""
    ensure_cache_dir()
    return os.path.join(CACHE_DIR, f"{symbol}_{data_type}.json")


def read_cache(symbol, data_type):
    """读取缓存数据"""
    cache_path = get_cache_path(symbol, data_type)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r') as f:
            cached = json.load(f)

        # 检查缓存是否过期
        cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
        ttl = CACHE_TTL.get(data_type, 3600)
        if datetime.now() - cache_time > timedelta(seconds=ttl):
            return None  # 缓存过期

        return cached.get('data')
    except:
        return None


def write_cache(symbol, data_type, data):
    """写入缓存数据"""
    cache_path = get_cache_path(symbol, data_type)
    try:
        with open(cache_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'data': data
            }, f, default=str)
    except Exception as e:
        print(f"Warning: Failed to write cache: {e}", file=sys.stderr)


# ==================== 公共辅助函数 ====================

def _extract_cashflow_for_year(cashflow, target_year):
    """从cashflow表中提取与target_year匹配的FCF相关字段"""
    result = {}
    if cashflow is None or cashflow.empty:
        return result
    cf_col = next((c for c in cashflow.columns if c.year == target_year), None)
    if cf_col is None:
        return result
    try:
        for key, row_name in [
            ('operating_cash_flow', 'Operating Cash Flow'),
            ('capital_expenditure', 'Capital Expenditure'),
            ('fcf', 'Free Cash Flow'),
        ]:
            if row_name in cashflow.index:
                val = cashflow.loc[row_name, cf_col]
                if pd.notna(val):
                    result[key] = float(val)
    except Exception as e:
        print(f"Warning: _extract_cashflow_for_year failed for {target_year}: {e}", file=sys.stderr)
    return result


def _correct_ev_ebitda(info):
    """
    修正 yfinance EV/EBITDA 的货币混用问题。
    对于中概股 ADR / 港股 ADR：EV 是交易货币（USD/HKD），EBITDA 是财务货币（CNY）。
    返回 (corrected_ratio_or_None, note_or_None)
    """
    ev_raw = info.get('enterpriseToEbitda')
    trading_currency = info.get('currency', 'USD')
    financial_currency = info.get('financialCurrency', trading_currency)

    if ev_raw is None:
        return None, None

    if financial_currency == trading_currency:
        return ev_raw, None

    ev = info.get('enterpriseValue')
    ebitda = info.get('ebitda')
    if not ev or not ebitda or ebitda == 0:
        return ev_raw, f'⚠️ EV/EBITDA 货币不一致（EV:{trading_currency} / EBITDA:{financial_currency}），数据存疑'

    try:
        fx_data = fetch_fx_rate_yfinance(trading_currency, financial_currency)
        fx = fx_data['rate'] if isinstance(fx_data, dict) else float(fx_data)
        corrected = (ev * fx) / ebitda
        return round(corrected, 2), f'已修正货币混用（EV {trading_currency}×{fx:.4f}={financial_currency}）'
    except Exception:
        return ev_raw, f'⚠️ EV/EBITDA 货币不一致（EV:{trading_currency} / EBITDA:{financial_currency}），汇率获取失败，请手动修正'


def _build_ttm_from_quarterly(quarterly_income, quarterly_cashflow):
    """从季报构造TTM（最近4个有效季度之和）"""
    if quarterly_income is None or quarterly_income.empty:
        return None
    try:
        # 找出Total Revenue有效（非NaN）的列，取最近4个
        if 'Total Revenue' not in quarterly_income.index:
            return None
        revenue_row = quarterly_income.loc['Total Revenue']
        valid_cols = [c for c in quarterly_income.columns if pd.notna(revenue_row[c])]
        if len(valid_cols) < 4:
            return None
        ttm_cols = valid_cols[:4]

        def sum_row(df, row_name):
            if row_name not in df.index:
                return None
            vals = [df.loc[row_name, c] for c in ttm_cols if pd.notna(df.loc[row_name, c])]
            return float(sum(vals)) if vals else None

        revenue = sum_row(quarterly_income, 'Total Revenue')
        net_income = sum_row(quarterly_income, 'Net Income')
        gross_profit = sum_row(quarterly_income, 'Gross Profit')

        if not revenue:
            return None

        quarters_used = []
        for c in ttm_cols:
            if hasattr(c, 'month'):
                qnum = (c.month - 1) // 3 + 1
                quarters_used.append(f"{c.year}-Q{qnum}")
            else:
                quarters_used.append(str(c))

        result = {
            'year': 'TTM',
            'data_note': f'季报聚合TTM（{quarters_used[0]}~{quarters_used[-1]}）',
            'revenue': revenue,
        }
        if net_income is not None:
            result['net_income'] = net_income
            result['net_margin'] = round(net_income / revenue * 100, 2)
        if gross_profit is not None:
            result['gross_profit'] = gross_profit
            result['gross_margin'] = round(gross_profit / revenue * 100, 2)

        # 季报现金流
        if quarterly_cashflow is not None and not quarterly_cashflow.empty:
            cf_cols = [c for c in quarterly_cashflow.columns if c in ttm_cols]
            def sum_cf(row_name):
                if row_name not in quarterly_cashflow.index:
                    return None
                vals = [quarterly_cashflow.loc[row_name, c] for c in cf_cols if pd.notna(quarterly_cashflow.loc[row_name, c])]
                return float(sum(vals)) if vals else None

            ocf = sum_cf('Operating Cash Flow')
            capex = sum_cf('Capital Expenditure')
            fcf = sum_cf('Free Cash Flow')
            if ocf is not None:
                result['operating_cash_flow'] = ocf
            if capex is not None:
                result['capital_expenditure'] = capex
            if fcf is not None:
                result['fcf'] = fcf
                result['fcf_margin'] = round(fcf / revenue * 100, 2)

        return result
    except Exception as e:
        print(f"Warning: _build_ttm_from_quarterly failed: {e}", file=sys.stderr)
        return None


def _build_quarterly_history(quarterly_income, quarterly_cashflow=None):
    """
    从季报构造最近8个季度的明细列表（含 YoY 同比、FCF、毛利率/净利率）。
    取8个季度是为了给最近4个季度计算 YoY（去年同期对比）。
    """
    if quarterly_income is None or quarterly_income.empty:
        return []
    try:
        # 跳过 revenue 为 NaN 的占位列（如未披露的最新季度），保留8个有效季度
        if 'Total Revenue' in quarterly_income.index:
            rev_row = quarterly_income.loc['Total Revenue']
            cols = [c for c in quarterly_income.columns if pd.notna(rev_row[c])][:8]
        else:
            cols = list(quarterly_income.columns[:8])
        raw = []
        for col in cols:
            try:
                q = {}
                if hasattr(col, 'month'):
                    qnum = (col.month - 1) // 3 + 1
                    q['quarter'] = f"{col.year}-Q{qnum}"
                else:
                    q['quarter'] = str(col)

                # 损益表字段
                for field, row_name in [
                    ('revenue',          'Total Revenue'),
                    ('net_income',       'Net Income'),
                    ('gross_profit',     'Gross Profit'),
                    ('operating_income', 'Operating Income'),
                    ('eps',              'Basic EPS'),
                ]:
                    if row_name in quarterly_income.index:
                        val = quarterly_income.loc[row_name, col]
                        if pd.notna(val):
                            q[field] = float(val)

                # 现金流字段（按季度匹配）
                if quarterly_cashflow is not None and not quarterly_cashflow.empty and hasattr(col, 'month'):
                    cf_col = next(
                        (c for c in quarterly_cashflow.columns
                         if hasattr(c, 'month') and c.year == col.year
                         and (c.month - 1) // 3 == (col.month - 1) // 3),
                        None
                    )
                    if cf_col is not None:
                        for cf_field, cf_row in [
                            ('operating_cash_flow', 'Operating Cash Flow'),
                            ('capital_expenditure', 'Capital Expenditure'),
                            ('fcf',                 'Free Cash Flow'),
                        ]:
                            if cf_row in quarterly_cashflow.index:
                                val = quarterly_cashflow.loc[cf_row, cf_col]
                                if pd.notna(val):
                                    q[cf_field] = float(val)
                        # FCF 降级：若无直接字段，从 OCF - |CAPEX| 计算
                        if 'fcf' not in q and q.get('operating_cash_flow') is not None \
                                and q.get('capital_expenditure') is not None:
                            q['fcf'] = q['operating_cash_flow'] - abs(q['capital_expenditure'])

                # 利润率
                if q.get('revenue') and q.get('gross_profit'):
                    q['gross_margin'] = round(q['gross_profit'] / q['revenue'] * 100, 2)
                if q.get('revenue') and q.get('net_income'):
                    q['net_margin'] = round(q['net_income'] / q['revenue'] * 100, 2)

                raw.append(q)
            except Exception:
                continue

        # 计算最近4个季度的 YoY（与4个季度前对比）
        for i in range(min(4, len(raw))):
            if i + 4 < len(raw):
                curr, prev = raw[i], raw[i + 4]
                if curr.get('revenue') and prev.get('revenue') and prev['revenue'] != 0:
                    curr['revenue_yoy'] = round(
                        (curr['revenue'] / prev['revenue'] - 1) * 100, 2)
                if curr.get('net_income') and prev.get('net_income') and prev['net_income'] != 0:
                    curr['net_income_yoy'] = round(
                        (curr['net_income'] / prev['net_income'] - 1) * 100, 2)
                if curr.get('gross_margin') is not None and prev.get('gross_margin') is not None:
                    curr['gross_margin_yoy_chg'] = round(
                        curr['gross_margin'] - prev['gross_margin'], 2)

        return raw
    except Exception as e:
        print(f"Warning: _build_quarterly_history failed: {e}", file=sys.stderr)
        return []


def compute_quarterly_momentum(quarterly_history):
    """
    从 _build_quarterly_history 输出推导季度增长动量。
    返回 TTM 财务数据、同比趋势、增速加速/减速判断、建议 CAGR 区间。
    quarterly_history 为最新季度在前的列表。
    """
    if not quarterly_history:
        return None

    recent_4 = quarterly_history[:4]

    # TTM：最近4个季度加总
    def ttm_sum(field):
        vals = [q[field] for q in recent_4 if q.get(field) is not None]
        return round(sum(vals), 2) if vals else None

    ttm_revenue          = ttm_sum('revenue')
    ttm_net_income       = ttm_sum('net_income')
    ttm_fcf              = ttm_sum('fcf')
    ttm_operating_income = ttm_sum('operating_income')

    # 利润率：4季度均值（消除季节性波动）
    def avg_margin(field):
        vals = [q[field] for q in recent_4 if q.get(field) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    avg_gross_margin = avg_margin('gross_margin')
    avg_net_margin   = avg_margin('net_margin')

    # YoY 趋势（最新在前）
    yoy_list = [q['revenue_yoy'] for q in recent_4 if 'revenue_yoy' in q]
    if not yoy_list:
        return {
            'ttm_revenue': ttm_revenue,
            'ttm_net_income': ttm_net_income,
            'ttm_fcf': ttm_fcf,
            'ttm_operating_income': ttm_operating_income,
            'avg_gross_margin_4q': avg_gross_margin,
            'avg_net_margin_4q': avg_net_margin,
            'revenue_yoy_trend': [],
            'note': '季度 YoY 数据不足，建议手动输入 CAGR',
        }

    avg_yoy = sum(yoy_list) / len(yoy_list)

    # 加速度：最近2季均值 vs 之前2季均值（正值=加速）
    if len(yoy_list) >= 4:
        acceleration = round(sum(yoy_list[:2]) / 2 - sum(yoy_list[2:]) / 2, 2)
    elif len(yoy_list) >= 2:
        acceleration = round(yoy_list[0] - yoy_list[-1], 2)
    else:
        acceleration = None

    if acceleration is None:
        trend = 'insufficient_data'
    elif acceleration > 3:
        trend = 'accelerating'
    elif acceleration < -3:
        trend = 'decelerating'
    else:
        trend = 'stable'

    # 建议 CAGR 区间（年化，基于季度 YoY 均值）
    base_cagr = round(avg_yoy / 100, 4)
    bear_cagr = round(base_cagr * 0.65, 4)                          # 增速降 35%
    bull_cagr = round(min(base_cagr * 1.35, base_cagr + 0.15), 4)  # 增速提 35%，但最多+15pp

    return {
        'revenue_yoy_trend':     [round(y, 2) for y in yoy_list],
        'avg_revenue_yoy':       round(avg_yoy, 2),
        'acceleration':          acceleration,
        'trend':                 trend,
        'avg_gross_margin_4q':   avg_gross_margin,
        'avg_net_margin_4q':     avg_net_margin,
        'ttm_revenue':           ttm_revenue,
        'ttm_net_income':        ttm_net_income,
        'ttm_fcf':               ttm_fcf,
        'ttm_operating_income':  ttm_operating_income,
        'suggested_bear_cagr':   bear_cagr,
        'suggested_base_cagr':   base_cagr,
        'suggested_bull_cagr':   bull_cagr,
        'cagr_basis':            f'基于最近{len(yoy_list)}个季度营收同比均值 {avg_yoy:.1f}%（{trend}）',
    }


# ==================== SEC EDGAR 数据源（美股官方年报）====================

_SEC_HEADERS = {'User-Agent': 'investment-analysis-tool research@opensource.example.com'}


def _get_cik_from_ticker(ticker):
    """从 SEC 官方 company_tickers.json 查 CIK（返回10位零填充字符串）"""
    import urllib.request
    req = urllib.request.Request(
        'https://www.sec.gov/files/company_tickers.json',
        headers=_SEC_HEADERS
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        mapping = json.loads(resp.read())
    ticker_upper = ticker.upper()
    for item in mapping.values():
        if item['ticker'].upper() == ticker_upper:
            return str(item['cik_str']).zfill(10)
    raise ValueError(f"Ticker '{ticker}' not found in SEC company_tickers.json")


def _fetch_sec_concept(cik_padded, concept, unit='USD'):
    """
    获取单个 us-gaap 概念的年报历史值。
    返回 {fiscal_year_str: entry_dict}，只保留 10-K/20-F 的 FY 期数据，
    同一财年取最新修订版。
    """
    import urllib.request
    url = f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik_padded}/us-gaap/{concept}.json'
    req = urllib.request.Request(url, headers=_SEC_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        entries = data.get('units', {}).get(unit, [])
        annual = [e for e in entries
                  if e.get('form') in ('10-K', '20-F') and e.get('fp') == 'FY']
        annual.sort(key=lambda x: x.get('filed', ''), reverse=True)
        seen = {}
        for e in annual:
            fy = str(e.get('fy') or e['end'][:4])
            if fy not in seen:
                seen[fy] = e
        return seen
    except Exception:
        return {}


def _build_sec_quarterly_history(cik_padded):
    """
    从 SEC EDGAR 10-Q 独立季度条目（~90天）构造最近8季度历史。
    使用 (fy, fp) 键匹配同期 YoY，不依赖 Q4 派生，避免缺季问题。
    返回格式与 _build_quarterly_history 一致（最新季度在前）。
    """
    import urllib.request

    def _get_standalone(concept, unit='USD'):
        """返回 {(fy_str, fp_str): {'val': ..., 'end': ..., 'filed': ...}}"""
        try:
            url = (f'https://data.sec.gov/api/xbrl/companyconcept/'
                   f'CIK{cik_padded}/us-gaap/{concept}.json')
            req = urllib.request.Request(url, headers=_SEC_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception:
            return {}

        entries = data.get('units', {}).get(unit, [])
        result = {}
        for e in entries:
            form  = e.get('form', '')
            fp    = e.get('fp', '')
            start = e.get('start')
            end   = e.get('end')
            fy    = str(e.get('fy', ''))
            filed = e.get('filed', '')

            if form != '10-Q' or fp not in ('Q1', 'Q2', 'Q3') or not start or not end:
                continue
            try:
                dur = (datetime.strptime(end, '%Y-%m-%d')
                       - datetime.strptime(start, '%Y-%m-%d')).days
            except Exception:
                continue
            if not (75 <= dur <= 105):
                continue

            key = (fy, fp)
            if key not in result or filed > result[key]['filed']:
                result[key] = {'val': e.get('val'), 'end': end, 'filed': filed}
        return result

    # Revenue: try ASC 606 → older concepts
    rev_map = {}
    for concept in ['RevenueFromContractWithCustomerExcludingAssessedTax',
                    'Revenues', 'SalesRevenueNet']:
        rev_map = _get_standalone(concept)
        if rev_map:
            break
    if not rev_map:
        return []

    ni_map = _get_standalone('NetIncomeLoss')
    gp_map = _get_standalone('GrossProfit')

    # Sort keys by end_date desc, take 8 most recent quarters
    keys_sorted = sorted(rev_map.keys(),
                         key=lambda k: rev_map[k]['end'], reverse=True)[:8]

    raw = []
    for fy, fp in keys_sorted:
        end_date = rev_map[(fy, fp)]['end']
        try:
            dt = datetime.strptime(end_date, '%Y-%m-%d')
            quarter_label = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
        except Exception:
            quarter_label = f"{fy}-{fp}"

        q = {'quarter': quarter_label, '_fy': fy, '_fp': fp}

        rv = rev_map.get((fy, fp))
        if rv:
            q['revenue'] = rv['val']
        ni = ni_map.get((fy, fp))
        if ni:
            q['net_income'] = ni['val']
        gp = gp_map.get((fy, fp))
        if gp:
            q['gross_profit'] = gp['val']

        if q.get('revenue') and q.get('gross_profit'):
            q['gross_margin'] = round(q['gross_profit'] / q['revenue'] * 100, 2)
        if q.get('revenue') and q.get('net_income'):
            q['net_margin'] = round(q['net_income'] / q['revenue'] * 100, 2)

        raw.append(q)

    # YoY: match same (fp) in (fy - 1)
    by_key = {(q['_fy'], q['_fp']): q for q in raw}
    for q in raw:
        fy, fp = q.get('_fy'), q.get('_fp')
        if not fy:
            continue
        try:
            prev_fy = str(int(fy) - 1)
        except ValueError:
            continue
        prev = by_key.get((prev_fy, fp))
        if not prev:
            continue
        if q.get('revenue') and prev.get('revenue') and prev['revenue'] != 0:
            q['revenue_yoy'] = round((q['revenue'] / prev['revenue'] - 1) * 100, 2)
        if q.get('net_income') and prev.get('net_income') and prev['net_income'] != 0:
            q['net_income_yoy'] = round(
                (q['net_income'] / prev['net_income'] - 1) * 100, 2)
        if q.get('gross_margin') is not None and prev.get('gross_margin') is not None:
            q['gross_margin_yoy_chg'] = round(q['gross_margin'] - prev['gross_margin'], 2)

    return raw


def fetch_us_stock_sec_edgar(symbol):
    """
    从 SEC EDGAR XBRL API 拉取美股官方年报财务数据。
    只返回 financial_history，不含行情/估值倍数。
    """
    import urllib.request

    # 1. ticker → CIK
    cik = _get_cik_from_ticker(symbol)

    # 2. 公司名称
    req = urllib.request.Request(
        f'https://data.sec.gov/submissions/CIK{cik}.json',
        headers=_SEC_HEADERS
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        sub_data = json.loads(resp.read())
    company_name = sub_data.get('name', '')

    # 3. 拉取各财务概念
    # 营收：ASC 606 新准则 → 旧准则兜底
    revenues = {}
    for concept in [
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'Revenues',
        'SalesRevenueNet',
    ]:
        revenues = _fetch_sec_concept(cik, concept)
        if revenues:
            break

    net_incomes     = _fetch_sec_concept(cik, 'NetIncomeLoss')
    gross_profits   = _fetch_sec_concept(cik, 'GrossProfit')
    op_incomes      = _fetch_sec_concept(cik, 'OperatingIncomeLoss')
    op_cashflows    = _fetch_sec_concept(cik, 'NetCashProvidedByUsedInOperatingActivities')
    capex           = _fetch_sec_concept(cik, 'PaymentsToAcquirePropertyPlantAndEquipment')
    total_assets    = _fetch_sec_concept(cik, 'Assets')
    total_equity    = _fetch_sec_concept(cik, 'StockholdersEquity')
    eps_diluted     = _fetch_sec_concept(cik, 'EarningsPerShareDiluted', unit='USD/shares')

    # 4. 合并为 financial_history（最近5年，年份降序）
    all_years = sorted(revenues.keys(), reverse=True)[:5] if revenues else \
                sorted(net_incomes.keys(), reverse=True)[:5]

    financial_history = []
    for year in all_years:
        row = {'year': year}
        if year in revenues:        row['revenue']             = revenues[year]['val']
        if year in net_incomes:     row['net_income']          = net_incomes[year]['val']
        if year in gross_profits:   row['gross_profit']        = gross_profits[year]['val']
        if year in op_incomes:      row['operating_income']    = op_incomes[year]['val']
        if year in op_cashflows:    row['operating_cash_flow'] = op_cashflows[year]['val']
        if year in capex:           row['capital_expenditure'] = capex[year]['val']
        if year in total_assets:    row['total_assets']        = total_assets[year]['val']
        if year in total_equity:    row['total_equity']        = total_equity[year]['val']
        if year in eps_diluted:     row['eps']                 = eps_diluted[year]['val']

        # 衍生指标
        if row.get('revenue') and row.get('gross_profit'):
            row['gross_margin'] = round(row['gross_profit'] / row['revenue'] * 100, 2)
        if row.get('revenue') and row.get('net_income'):
            row['net_margin'] = round(row['net_income'] / row['revenue'] * 100, 2)
        if row.get('operating_cash_flow') is not None and row.get('capital_expenditure') is not None:
            row['fcf'] = row['operating_cash_flow'] - row['capital_expenditure']
            if row.get('revenue'):
                row['fcf_margin'] = round(row['fcf'] / row['revenue'] * 100, 2)
        if row.get('net_income') and row.get('total_equity') and row['total_equity'] != 0:
            row['roe'] = round(row['net_income'] / row['total_equity'], 4)

        financial_history.append(row)

    # 5. 季度历史（10-Q standalone，用于 YoY momentum）
    try:
        sec_quarterly_history = _build_sec_quarterly_history(cik)
    except Exception as e:
        print(f"Warning: SEC quarterly history failed for {symbol}: {e}", file=sys.stderr)
        sec_quarterly_history = []

    return {
        'source': 'sec_edgar',
        'market': '美股',
        'symbol': symbol,
        'cik': cik,
        'company_name': company_name,
        'financial_history': financial_history,
        'quarterly_history': sec_quarterly_history,
        'timestamp': datetime.now().isoformat(),
    }


# ==================== 美股数据抓取（多层级）====================

def fetch_us_stock_yfinance(symbol):
    """层级1: yfinance获取美股数据"""
    try:
        import yfinance as yf

        tk = yf.Ticker(symbol)
        info = tk.info

        # 提取5年财务历史（年报）
        income = tk.financials
        cashflow = tk.cashflow
        financial_history = []
        if not income.empty:
            for col in income.columns[:5]:
                try:
                    year_data = {'year': str(col.year)}
                    if 'Total Revenue' in income.index:
                        year_data['revenue'] = float(income.loc['Total Revenue', col])
                    if 'Net Income' in income.index:
                        year_data['net_income'] = float(income.loc['Net Income', col])
                    if 'Gross Profit' in income.index:
                        year_data['gross_profit'] = float(income.loc['Gross Profit', col])

                    # 计算比率
                    if year_data.get('revenue') and year_data.get('gross_profit'):
                        year_data['gross_margin'] = round(year_data['gross_profit'] / year_data['revenue'] * 100, 2)
                    if year_data.get('revenue') and year_data.get('net_income'):
                        year_data['net_margin'] = round(year_data['net_income'] / year_data['revenue'] * 100, 2)

                    # FCF数据
                    cf = _extract_cashflow_for_year(cashflow, col.year)
                    year_data.update(cf)
                    if year_data.get('revenue') and year_data.get('fcf'):
                        year_data['fcf_margin'] = round(year_data['fcf'] / year_data['revenue'] * 100, 2)

                    financial_history.append(year_data)
                except:
                    continue

        # 季报数据（用于TTM降级和季度明细）
        quarterly_income = tk.quarterly_income_stmt
        quarterly_cashflow = tk.quarterly_cashflow
        quarterly_history = _build_quarterly_history(quarterly_income, quarterly_cashflow)
        quarterly_momentum = compute_quarterly_momentum(quarterly_history)

        # 若最新年报收入为NaN（未披露Q4），用季报TTM替换
        import math
        first_rev = financial_history[0].get('revenue') if financial_history else None
        first_rev_nan = (first_rev is None) or (isinstance(first_rev, float) and math.isnan(first_rev))
        if first_rev_nan:
            ttm = _build_ttm_from_quarterly(quarterly_income, quarterly_cashflow)
            if ttm:
                if financial_history:
                    financial_history[0] = ttm
                else:
                    financial_history = [ttm]

        return {
            'source': 'yfinance',
            'market': '美股',
            'symbol': symbol,
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
                'ev_to_ebitda': _correct_ev_ebitda(info)[0],
                'ev_to_ebitda_note': _correct_ev_ebitda(info)[1],
                'enterprise_value': info.get('enterpriseValue'),
                'ebitda': info.get('ebitda'),
                'dividend_yield': info.get('dividendYield'),
                'payout_ratio': info.get('payoutRatio'),
                'current_price': info.get('currentPrice') or info.get('regularMarketPrice'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            },
            'financial_history': financial_history,
            'quarterly_history': quarterly_history,
            'quarterly_momentum': quarterly_momentum,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        raise Exception(f"yfinance failed: {e}")


def fetch_us_stock_alphavantage(symbol, api_key=None):
    """层级2: Alpha Vantage获取美股数据（备用）"""
    # 需要API key，这里仅作为结构示例
    raise Exception("Alpha Vantage需要API key")


def fetch_us_stock_cached(symbol):
    """层级3: 读取缓存数据"""
    cached = read_cache(symbol, 'financials')
    if cached:
        cached['source'] = 'cache'
        cached['warning'] = '使用缓存数据，可能不是最新'
        return cached
    raise Exception("无可用缓存")


def fetch_us_stock_data(symbol):
    """美股数据抓取（带降级）
    L1a yfinance  : 实时行情 + 估值倍数 + 财报（备用）
    L1b SEC EDGAR : 官方年报财务数据，覆盖 financial_history
    两者并行拉取后合并；任一失败则另一方独立兜底。
    """
    errors = []
    yfinance_result = None
    sec_result = None

    # L1a: yfinance
    try:
        yfinance_result = fetch_us_stock_yfinance(symbol)
    except Exception as e:
        errors.append(f"yfinance: {e}")
        print(f"Warning: yfinance failed for {symbol}: {e}", file=sys.stderr)

    # L1b: SEC EDGAR（官方财报，覆盖 financial_history）
    try:
        sec_result = fetch_us_stock_sec_edgar(symbol)
    except Exception as e:
        errors.append(f"sec_edgar: {e}")
        print(f"Warning: SEC EDGAR failed for {symbol}: {e}", file=sys.stderr)

    # 合并：yfinance 提供行情/估值，SEC 覆盖 financial_history 和 quarterly_history
    if yfinance_result and sec_result:
        # 智能合并 financial_history：
        # SEC 是权威年报来源（USD），但可能缺当年数据（20-F 归档延迟）。
        # 当 SEC 最新年份 < 当前年 且 yfinance 有 TTM，则将 yfinance TTM 前置（标注 RMB）。
        sec_fh = sec_result['financial_history']
        yf_fh  = yfinance_result.get('financial_history', [])
        sec_max_year = max((f['year'] for f in sec_fh), default='0')
        current_year = str(datetime.now().year)
        yf_ttm = next((f for f in yf_fh if f.get('year') == 'TTM'), None)
        if yf_ttm and sec_max_year < current_year:
            yf_ttm_copy = dict(yf_ttm)
            yf_ttm_copy['currency_note'] = 'RMB（yfinance季报聚合，非USD）'
            yfinance_result['financial_history'] = [yf_ttm_copy] + sec_fh
        else:
            yfinance_result['financial_history'] = sec_fh
        yfinance_result['cik'] = sec_result['cik']
        yfinance_result['source'] = 'yfinance+sec_edgar'

        # 若 SEC 季度历史 YoY 数据更多，用 SEC 替换并补充 FCF（来自 yfinance）
        sec_qh = sec_result.get('quarterly_history', [])
        yf_qh = yfinance_result.get('quarterly_history', [])
        sec_yoy = sum(1 for q in sec_qh if 'revenue_yoy' in q)
        yf_yoy  = sum(1 for q in yf_qh if 'revenue_yoy' in q)
        if sec_yoy > yf_yoy and sec_qh:
            # 将 yfinance 的 FCF 数据按季度标签回填到 SEC 记录中
            yf_fcf_map = {q['quarter']: q for q in yf_qh if q.get('fcf') is not None}
            for q in sec_qh:
                if q.get('fcf') is None:
                    yf_q = yf_fcf_map.get(q['quarter'])
                    if yf_q:
                        for fcf_field in ('fcf', 'operating_cash_flow', 'capital_expenditure'):
                            if yf_q.get(fcf_field) is not None:
                                q[fcf_field] = yf_q[fcf_field]
            yfinance_result['quarterly_history'] = sec_qh
            yfinance_result['quarterly_momentum'] = compute_quarterly_momentum(sec_qh)

        write_cache(symbol, 'financials', yfinance_result)
        return yfinance_result

    if yfinance_result:
        write_cache(symbol, 'financials', yfinance_result)
        return yfinance_result

    if sec_result:
        write_cache(symbol, 'financials', sec_result)
        return sec_result

    # L2: Alpha Vantage
    try:
        result = fetch_us_stock_alphavantage(symbol)
        write_cache(symbol, 'financials', result)
        return result
    except Exception as e:
        errors.append(f"AlphaVantage: {e}")

    # L3: 缓存兜底
    try:
        result = fetch_us_stock_cached(symbol)
        return result
    except Exception as e:
        errors.append(f"cache: {e}")

    # 全部失败
    return {
        'error': '所有数据源均失败',
        'details': errors,
        'market': '美股',
        'symbol': symbol
    }


# ==================== A股数据抓取（多层级） ====================

def fetch_a_stock_akshare(symbol):
    """层级1: akshare获取A股数据"""
    try:
        import akshare as ak

        # 实时行情
        realtime = ak.stock_zh_a_spot_em()
        stock_info = realtime[realtime['代码'] == symbol]

        # 历史行情
        hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20190101", adjust="hfq")

        # 财务摘要
        financials = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按年度")

        return {
            'source': 'akshare',
            'market': 'A股',
            'symbol': symbol,
            'realtime': stock_info.to_dict('records')[0] if not stock_info.empty else {},
            'history': hist.tail(252).to_dict('records') if not hist.empty else [],
            'financials': financials.to_dict('records') if not financials.empty else [],
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        raise Exception(f"akshare failed: {e}")


def fetch_a_stock_sina(symbol):
    """层级2: 新浪财经获取A股实时行情"""
    try:
        import urllib.request

        # 转换代码格式
        prefix = 'sh' if symbol.startswith('6') else 'sz'
        url = f"https://hq.sinajs.cn/list={prefix}{symbol}"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        response = urllib.request.urlopen(req, timeout=5).read().decode("gbk")

        # 解析数据
        data = response.split('"')[1].split(',')
        if len(data) > 3:
            return {
                'source': 'sina',
                'market': 'A股',
                'symbol': symbol,
                'realtime': {
                    'name': data[0],
                    'open': float(data[1]),
                    'close': float(data[2]),
                    'current': float(data[3]),
                    'high': float(data[4]),
                    'low': float(data[5]),
                },
                'warning': '仅实时行情，无财报数据',
                'timestamp': datetime.now().isoformat()
            }
        raise Exception("解析失败")
    except Exception as e:
        raise Exception(f"sina failed: {e}")


def fetch_a_stock_data(symbol):
    """A股数据抓取（带降级）"""
    errors = []

    # 尝试层级1: akshare
    try:
        result = fetch_a_stock_akshare(symbol)
        write_cache(symbol, 'financials', result)
        return result
    except Exception as e:
        errors.append(f"akshare: {e}")

    # 尝试层级2: 新浪财经
    try:
        result = fetch_a_stock_sina(symbol)
        # 合并缓存的财报数据
        cached = read_cache(symbol, 'financials')
        if cached:
            result['financials'] = cached.get('financials', [])
        return result
    except Exception as e:
        errors.append(f"sina: {e}")

    # 层级3: 缓存兜底
    try:
        result = fetch_us_stock_cached(symbol)  # 复用缓存读取
        return result
    except Exception as e:
        errors.append(f"cache: {e}")

    return {
        'error': '所有数据源均失败',
        'details': errors,
        'market': 'A股',
        'symbol': symbol
    }


# ==================== 港股数据抓取 ====================

def fetch_hk_stock_yfinance(symbol):
    """层级1: yfinance获取港股数据（首选，稳定性更好）"""
    try:
        import yfinance as yf

        clean_symbol = symbol.replace('.HK', '')
        yf_symbol = f"{int(clean_symbol):04d}.HK"

        tk = yf.Ticker(yf_symbol)
        info = tk.info
        hist = tk.history(period="5y")

        # 提取财务历史（年报）
        income = tk.financials
        cashflow = tk.cashflow
        financial_history = []
        if not income.empty:
            for col in income.columns[:5]:
                try:
                    year_data = {'year': str(col.year)}
                    if 'Total Revenue' in income.index:
                        year_data['revenue'] = float(income.loc['Total Revenue', col])
                    if 'Net Income' in income.index:
                        year_data['net_income'] = float(income.loc['Net Income', col])
                    if 'Gross Profit' in income.index:
                        year_data['gross_profit'] = float(income.loc['Gross Profit', col])

                    if year_data.get('revenue') and year_data.get('gross_profit'):
                        year_data['gross_margin'] = round(year_data['gross_profit'] / year_data['revenue'] * 100, 2)
                    if year_data.get('revenue') and year_data.get('net_income'):
                        year_data['net_margin'] = round(year_data['net_income'] / year_data['revenue'] * 100, 2)

                    # FCF数据
                    cf = _extract_cashflow_for_year(cashflow, col.year)
                    year_data.update(cf)
                    if year_data.get('revenue') and year_data.get('fcf'):
                        year_data['fcf_margin'] = round(year_data['fcf'] / year_data['revenue'] * 100, 2)

                    financial_history.append(year_data)
                except:
                    continue

        # 季报数据（用于TTM降级和季度明细）
        quarterly_income = tk.quarterly_income_stmt
        quarterly_cashflow = tk.quarterly_cashflow
        quarterly_history = _build_quarterly_history(quarterly_income)

        # 若最新年报收入为NaN（未披露Q4），用季报TTM替换
        import math
        first_rev = financial_history[0].get('revenue') if financial_history else None
        first_rev_nan = (first_rev is None) or (isinstance(first_rev, float) and math.isnan(first_rev))
        if first_rev_nan:
            ttm = _build_ttm_from_quarterly(quarterly_income, quarterly_cashflow)
            if ttm:
                if financial_history:
                    financial_history[0] = ttm
                else:
                    financial_history = [ttm]

        return {
            'source': 'yfinance',
            'market': '港股',
            'symbol': symbol,
            'info': {
                'name': info.get('longName'),
                'sector': info.get('sector'),
                'market_cap': info.get('marketCap'),
                'shares_outstanding': info.get('sharesOutstanding'),
                'eps': info.get('trailingEps'),
                'pe': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb': info.get('priceToBook'),
                'roe': info.get('returnOnEquity'),
                'ev_to_ebitda': _correct_ev_ebitda(info)[0],
                'ev_to_ebitda_note': _correct_ev_ebitda(info)[1],
                'enterprise_value': info.get('enterpriseValue'),
                'ebitda': info.get('ebitda'),
                'dividend_yield': info.get('dividendYield'),
                'payout_ratio': info.get('payoutRatio'),
                'current_price': info.get('currentPrice') or info.get('regularMarketPrice'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            },
            'history': hist.tail(252).to_dict('records') if not hist.empty else [],
            'financial_history': financial_history,
            'quarterly_history': quarterly_history,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        raise Exception(f"yfinance failed: {e}")


def fetch_hk_stock_akshare(symbol):
    """层级2: akshare获取港股历史数据（备用）"""
    try:
        import akshare as ak
        clean_symbol = symbol.replace('.HK', '')
        hist = ak.stock_hk_hist(symbol=clean_symbol, period="daily", start_date="20190101", adjust="")

        return {
            'source': 'akshare',
            'market': '港股',
            'symbol': symbol,
            'history': hist.tail(252).to_dict('records') if not hist.empty else [],
            'warning': '仅历史行情数据',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        raise Exception(f"akshare failed: {e}")


def fetch_hk_stock_akshare_financials(symbol):
    """层级1.5: akshare获取港股完整财务数据（补充yfinance缺失的最新年报）"""
    try:
        import akshare as ak
        if pd is None:
            raise Exception("pandas not available")

        clean_symbol = symbol.replace('.HK', '').zfill(5)
        indicator = ak.stock_financial_hk_analysis_indicator_em(symbol=clean_symbol)

        if indicator.empty:
            raise Exception("akshare返回空数据")

        # 尝试从报告日期列提取年份，否则按行序降序推算
        date_col = next((c for c in indicator.columns if 'DATE' in c.upper() or '日期' in c), None)
        current_year = datetime.now().year

        financial_history = []
        for i, (_, row) in enumerate(indicator.iterrows()):
            try:
                if date_col and pd.notna(row[date_col]):
                    year = str(pd.to_datetime(row[date_col]).year)
                else:
                    year = str(current_year - i)

                def safe_float(val):
                    return float(val) if pd.notna(val) else None

                gp = safe_float(row.get('GROSS_PROFIT'))
                rev = safe_float(row.get('OPERATE_INCOME'))
                ni = safe_float(row.get('HOLDER_PROFIT'))
                gm = safe_float(row.get('GROSS_PROFIT_RATIO'))
                nm = safe_float(row.get('NET_PROFIT_RATIO'))

                financial_history.append({
                    'year': year,
                    'revenue': rev,
                    'net_income': ni,
                    'gross_profit': gp,
                    'eps': safe_float(row.get('BASIC_EPS')),
                    'roe': safe_float(row.get('ROE_AVG')),
                    'gross_margin': gm if gm else (round(gp / rev * 100, 2) if gp and rev else None),
                    'net_margin': nm if nm else (round(ni / rev * 100, 2) if ni and rev else None),
                })
            except Exception:
                continue

        # 实时行情（作为价格补充）
        realtime = None
        try:
            hk_spot = ak.stock_hk_spot_em()
            row = hk_spot[hk_spot['代码'] == clean_symbol]
            if not row.empty:
                r = row.iloc[0]
                realtime = {
                    'current_price': float(r['最新价']) if pd.notna(r['最新价']) else None,
                    'market_cap': float(r['总市值']) * 10000 if pd.notna(r.get('总市值')) else None,
                    'pe': float(r['市盈率']) if pd.notna(r.get('市盈率')) else None,
                    'pb': float(r['市净率']) if pd.notna(r.get('市净率')) else None,
                }
        except Exception as e:
            print(f"Warning: akshare realtime price fetch failed: {e}", file=sys.stderr)
            pass

        return {
            'source': 'akshare_financials',
            'market': '港股',
            'symbol': symbol,
            'info': {
                'name': name,
                'current_price': realtime.get('current_price') if realtime else None,
                'market_cap': realtime.get('market_cap') if realtime else None,
                'eps': latest.get('eps'),
                'pe': realtime.get('pe') if realtime else None,
                'pb': realtime.get('pb') if realtime else None,
                'roe': latest.get('roe'),
            },
            'financial_history': financial_history,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        raise Exception(f"akshare_financials failed: {e}")


def _hk_financial_data_valid(result):
    """检查财务历史是否包含近两年数据（2024或2025）"""
    history = result.get('financial_history', []) if result else []
    if len(history) < 3:
        return False
    years = {h.get('year') for h in history}
    return bool(years & {str(datetime.now().year), str(datetime.now().year - 1)})


def _merge_hk_data(yf_result, ak_result):
    """合并yfinance（实时价格）和akshare（最新财务）的数据"""
    yf_info = yf_result.get('info', {}) if yf_result else {}
    ak_info = ak_result.get('info', {}) if ak_result else {}

    return {
        'source': 'yfinance+akshare',
        'market': '港股',
        'symbol': yf_result.get('symbol') or ak_result.get('symbol'),
        'info': {
            'name': yf_info.get('name') or ak_info.get('name'),
            'sector': yf_info.get('sector'),
            'market_cap': yf_info.get('market_cap') or ak_info.get('market_cap'),
            'shares_outstanding': yf_info.get('shares_outstanding'),
            'eps': ak_info.get('eps') or yf_info.get('eps'),
            'pe': yf_info.get('pe') or ak_info.get('pe'),
            'forward_pe': yf_info.get('forward_pe'),
            'pb': yf_info.get('pb') or ak_info.get('pb'),
            'roe': ak_info.get('roe') or yf_info.get('roe'),
            'current_price': yf_info.get('current_price') or ak_info.get('current_price'),
            'fifty_two_week_high': yf_info.get('fifty_two_week_high'),
            'fifty_two_week_low': yf_info.get('fifty_two_week_low'),
        },
        'history': (yf_result or {}).get('history', []),
        'financial_history': ak_result.get('financial_history') or yf_result.get('financial_history', []),
        'data_source_note': '价格来自yfinance，财务数据来自akshare（含最新年报）',
        'timestamp': datetime.now().isoformat()
    }


def fetch_hk_stock_data(symbol):
    """港股数据抓取（yfinance首选 + akshare财务补充 + akshare行情备用 + 缓存兜底）"""
    errors = []
    yf_result = None

    # 层级1: yfinance（实时价格 + 基本信息）
    try:
        yf_result = fetch_hk_stock_yfinance(symbol)
        # 财务数据完整则直接返回，否则继续尝试akshare补充
        if _hk_financial_data_valid(yf_result):
            write_cache(symbol, 'financials', yf_result)
            return yf_result
        else:
            errors.append("yfinance: 财务历史缺少最新年度数据，尝试akshare补充")
    except Exception as e:
        errors.append(f"yfinance: {e}")

    # 层级1.5: akshare财务数据（补充最新年报 / 当yfinance完全失败时作为信息源）
    try:
        ak_fin = fetch_hk_stock_akshare_financials(symbol)
        merged = _merge_hk_data(yf_result, ak_fin)
        write_cache(symbol, 'financials', merged)
        return merged
    except Exception as e:
        errors.append(f"akshare_financials: {e}")

    # yfinance有数据但财务不完整，仍返回（标注缺失）
    if yf_result:
        yf_result['warning'] = '财务历史数据可能缺少最新年报'
        yf_result['degradation_errors'] = errors
        write_cache(symbol, 'financials', yf_result)
        return yf_result

    # 层级2: akshare历史行情（仅价格数据）
    try:
        result = fetch_hk_stock_akshare(symbol)
        cached = read_cache(symbol, 'financials')
        if cached and 'info' in cached:
            result['info'] = cached['info']
            result['financial_history'] = cached.get('financial_history', [])
        return result
    except Exception as e:
        errors.append(f"akshare: {e}")

    # 层级3: 缓存兜底
    try:
        result = fetch_us_stock_cached(symbol)
        return result
    except Exception as e:
        errors.append(f"cache: {e}")

    return {
        'error': '所有数据源均失败',
        'details': errors,
        'market': '港股',
        'symbol': symbol
    }


# ==================== 宏观数据 ====================

def _fetch_fred_latest(series_id):
    """从 FRED 获取最新数据点，无需 API key。返回 {'date', 'value', 'source'} 或 None。"""
    import requests
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    lines = [l for l in resp.text.strip().split('\n') if l and not l.startswith('DATE')]
    if not lines:
        return None
    parts = lines[-1].split(',')
    return {'date': parts[0], 'value': float(parts[1]), 'source': f'FRED({series_id})'}


def fetch_fx_rate_yfinance(base, quote):
    """使用yfinance获取实时汇率（如 base=USD, quote=CNY → USD/CNY）"""
    try:
        import yfinance as yf

        symbol = f"{quote}=X"
        fx = yf.Ticker(symbol)
        info = fx.info

        current_rate = info.get('regularMarketPrice')
        prev_close = info.get('regularMarketPreviousClose')

        if current_rate and prev_close:
            change_pct = round((current_rate - prev_close) / prev_close * 100, 2)
        else:
            change_pct = None

        return {
            'base': base,
            'quote': quote,
            'rate': current_rate,
            'previous_close': prev_close,
            'change_pct': change_pct,
            'timestamp': datetime.now().isoformat(),
            'source': 'yfinance'
        }
    except Exception as e:
        raise Exception(f"yfinance汇率获取失败: {e}")


def fetch_macro_data():
    """获取宏观数据（美联储利率、中美利差、实时汇率）"""
    result = {
        'timestamp': datetime.now().isoformat(),
        'source': 'multi',
        'errors': []
    }

    # 实时 USD/CNY 汇率
    try:
        result['fx_rate_usd_cny'] = fetch_fx_rate_yfinance('USD', 'CNY')
    except Exception as e:
        result['errors'].append(f'USD/CNY汇率: {e}')
        result['fx_rate_usd_cny'] = None

    # VIX 恐慌指数
    try:
        import yfinance as yf
        vix = yf.Ticker('^VIX').info
        result['vix'] = {
            'value': vix.get('regularMarketPrice'),
            'previous_close': vix.get('regularMarketPreviousClose'),
            'source': 'yfinance',
        }
    except Exception as e:
        result['errors'].append(f'VIX: {e}')
        result['vix'] = None

    # 美国10年期国债收益率（L1: yfinance ^TNX → L2: FRED DGS10）
    try:
        import yfinance as yf
        tnx = yf.Ticker('^TNX').info
        val = tnx.get('regularMarketPrice')
        if val:
            result['us_10y_yield'] = {
                'value': val,
                'previous_close': tnx.get('regularMarketPreviousClose'),
                'source': 'yfinance(^TNX)',
            }
        else:
            raise ValueError('yfinance returned None for ^TNX')
    except Exception as e:
        result['errors'].append(f'US10Y yfinance: {e}')
        try:
            fred = _fetch_fred_latest('DGS10')
            result['us_10y_yield'] = fred  # already has 'source' key
        except Exception as e2:
            result['errors'].append(f'US10Y FRED: {e2}')
            result['us_10y_yield'] = None

    # 实时 USD/CNH 离岸汇率
    try:
        result['fx_rate_usd_cnh'] = fetch_fx_rate_yfinance('USD', 'CNH')
    except Exception as e:
        result['errors'].append(f'USD/CNH汇率: {e}')
        result['fx_rate_usd_cnh'] = None

    # 实时 USD/HKD 汇率
    try:
        result['fx_rate_usd_hkd'] = fetch_fx_rate_yfinance('USD', 'HKD')
    except Exception as e:
        result['errors'].append(f'USD/HKD汇率: {e}')
        result['fx_rate_usd_hkd'] = None

    # 美联储利率（L1: akshare → L2: FRED FEDFUNDS）
    try:
        import akshare as ak
        fed_rate = ak.macro_bank_usa_interest_rate()
        result['fed_rate'] = fed_rate.tail(3).to_dict('records') if not fed_rate.empty else []
        if not result['fed_rate']:
            raise ValueError('akshare returned empty fed_rate')
    except Exception as e:
        result['errors'].append(f'美联储利率 akshare: {e}')
        try:
            fred = _fetch_fred_latest('FEDFUNDS')
            result['fed_rate'] = [fred] if fred else []
        except Exception as e2:
            result['errors'].append(f'美联储利率 FRED: {e2}')
            result['fed_rate'] = []

    # 中国 LPR（L1: akshare → 失败则标注缺失，由流程层 WebFetch 补充）
    try:
        import akshare as ak
        lpr = ak.macro_china_lpr()
        result['china_lpr'] = lpr.tail(3).to_dict('records') if not lpr.empty else []
    except Exception as e:
        result['errors'].append(f'China LPR: {e}')
        result['china_lpr'] = []

    # 中美利率
    try:
        import akshare as ak
        us_cn_rate = ak.bond_zh_us_rate(start_date="20240101")
        result['us_cn_rate'] = us_cn_rate.tail(5).to_dict('records') if not us_cn_rate.empty else []
    except Exception as e:
        result['errors'].append(f'中美利率: {e}')
        result['us_cn_rate'] = []

    return result


# ==================== 主入口 ====================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python data_fetcher_v2.py us <symbol>  (美股: AAPL)")
        print("  python data_fetcher_v2.py a <symbol>   (A股: 600519)")
        print("  python data_fetcher_v2.py hk <symbol>  (港股: 00700)")
        print("  python data_fetcher_v2.py macro")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'us' and len(sys.argv) > 2:
        result = fetch_us_stock_data(sys.argv[2])
    elif cmd == 'a' and len(sys.argv) > 2:
        result = fetch_a_stock_data(sys.argv[2])
    elif cmd == 'hk' and len(sys.argv) > 2:
        result = fetch_hk_stock_data(sys.argv[2])
    elif cmd == 'macro':
        result = fetch_macro_data()
    else:
        print(f"Invalid command: {cmd}")
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
