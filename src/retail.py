"""可复用的清洗、指标与 RFM 函数；金额内部使用万分之一英镑整数。"""
from decimal import Decimal

import numpy as np
import pandas as pd

SOURCE_COLUMNS = ['invoice_no', 'stock_code', 'description', 'quantity',
                  'invoice_date', 'unit_price_units', 'customer_id', 'country']
RENAME = dict(zip(['InvoiceNo', 'StockCode', 'Description', 'Quantity',
                  'InvoiceDate', 'UnitPrice', 'CustomerID', 'Country'], SOURCE_COLUMNS))
SEGMENTS = ['重要价值客户', '重要发展客户', '重要保持客户', '重要挽留客户',
            '一般价值客户', '一般发展客户', '一般保持客户', '一般挽留客户']


def normalize(raw):
    """保留源 Excel 行号；不填补客户 ID，不把不同商品描述合并后去重。"""
    d = raw.rename(columns=RENAME).copy()
    d.insert(0, 'source_row', np.arange(2, len(d) + 2))
    for c in ['invoice_no', 'stock_code', 'description', 'country']:
        d[c] = d[c].astype('string').str.strip().replace('', pd.NA)
    d['customer_id'] = pd.to_numeric(d['customer_id'], errors='coerce').astype('Int64').astype('string')
    d['quantity'] = pd.to_numeric(d['quantity'], errors='coerce').astype('Int64')
    d['invoice_date'] = pd.to_datetime(d['invoice_date'], errors='coerce')

    def price_units(v):
        if pd.isna(v):
            return pd.NA
        scaled = Decimal(str(v)) * 10000
        if scaled != scaled.to_integral_value():
            raise ValueError(f'价格精度超过四位小数: {v}')
        return int(scaled)

    d['unit_price_units'] = d['unit_price_units'].map(price_units).astype('Int64')
    return d


def clean(d):
    """按互斥优先级标记剔除原因，保留所有记录供审计。"""
    a = d.copy()
    a['reason'] = 'retained'
    rules = [
        ('duplicate', d.duplicated(SOURCE_COLUMNS)),
        ('invalid_required', d[['invoice_no', 'stock_code', 'quantity', 'invoice_date', 'unit_price_units']].isna().any(axis=1)),
        ('cancelled', d['invoice_no'].str.upper().str.startswith('C').fillna(False)),
        ('nonpositive_quantity', d['quantity'].le(0).fillna(False)),
        ('nonpositive_price', d['unit_price_units'].le(0).fillna(False)),
    ]
    for reason, mask in rules:
        a.loc[(a['reason'] == 'retained') & mask, 'reason'] = reason
    a['amount_units'] = a['quantity'] * a['unit_price_units']
    a['is_merchandise'] = a['stock_code'].str.fullmatch(r'[0-9]{5}[A-Za-z]*').fillna(False)
    sales = a.loc[a['reason'] == 'retained'].copy()
    sales['month'] = sales['invoice_date'].dt.strftime('%Y-%m')
    sales['unit_price_gbp'] = sales['unit_price_units'] / 10000
    sales['amount_gbp'] = sales['amount_units'] / 10000
    return a, sales


def segment_scores(r, f, m):
    # 三个维度分别 >= 3 为高；M 决定重要/一般，R/F 决定运营类型。
    return np.select([
        (m >= 3) & (r >= 3) & (f >= 3),
        (m >= 3) & (r >= 3) & (f < 3),
        (m >= 3) & (r < 3) & (f >= 3),
        (m >= 3) & (r < 3) & (f < 3),
        (m < 3) & (r >= 3) & (f >= 3),
        (m < 3) & (r >= 3) & (f < 3),
        (m < 3) & (r < 3) & (f >= 3),
    ], SEGMENTS[:7], default=SEGMENTS[7])


def rfm_analysis(sales, reference_date):
    customers = sales.dropna(subset=['customer_id'])
    rfm = customers.groupby('customer_id').agg(
        last_purchase=('invoice_date', 'max'), frequency=('invoice_no', 'nunique'),
        monetary_units=('amount_units', 'sum')).reset_index()
    rfm['recency_days'] = (pd.Timestamp(reference_date) - rfm['last_purchase'].dt.normalize()).dt.days
    thresholds = {}
    for col, score, reverse in [('recency_days', 'r_score', True),
                                ('frequency', 'f_score', False),
                                ('monetary_units', 'm_score', False)]:
        cuts = rfm[col].quantile([.2, .4, .6, .8]).to_numpy(dtype=float)
        thresholds[col] = cuts.tolist()
        # 相同原始值同分；边界归入较低数值档。频次并列可能导致档位不等宽。
        rank = 1 + (rfm[col].to_numpy(dtype=float)[:, None] > cuts).sum(axis=1)
        rfm[score] = 6 - rank if reverse else rank
    rfm['monetary_gbp'] = rfm['monetary_units'] / 10000
    rfm['rfm_code'] = rfm[['r_score', 'f_score', 'm_score']].astype(str).agg(''.join, axis=1)
    rfm['segment'] = segment_scores(rfm.r_score, rfm.f_score, rfm.m_score)
    return rfm, thresholds


def summarize(sales, rfm):
    monthly = sales.groupby('month').agg(sales_units=('amount_units', 'sum'),
        orders=('invoice_no', 'nunique'), customers=('customer_id', 'nunique'),
        lines=('source_row', 'size')).reset_index()
    monthly['sales_gbp'] = monthly['sales_units'] / 10000
    monthly['aov_gbp'] = monthly['sales_gbp'] / monthly['orders']
    monthly['complete_month'] = monthly['month'] != sales['invoice_date'].max().strftime('%Y-%m')
    monthly['mom_sales'] = monthly['sales_gbp'].pct_change()
    monthly.loc[~monthly['complete_month'], 'mom_sales'] = np.nan
    orders = sales.groupby('invoice_no').agg(order_units=('amount_units', 'sum'),
        order_date=('invoice_date', 'min'), lines=('source_row', 'size')).reset_index()
    orders['order_gbp'] = orders['order_units'] / 10000
    products = sales[sales['is_merchandise']].groupby('stock_code').agg(
        sales_units=('amount_units', 'sum'), quantity=('quantity', 'sum'),
        orders=('invoice_no', 'nunique')).reset_index()
    # 描述有变体：展示最后一个非空描述，汇总主键始终为 StockCode。
    descriptions = sales.dropna(subset=['description']).sort_values(['invoice_date', 'source_row']).drop_duplicates('stock_code', keep='last')
    products = products.merge(descriptions[['stock_code', 'description']], on='stock_code', how='left')
    products = products.sort_values(['sales_units', 'stock_code'], ascending=[False, True]).reset_index(drop=True)
    products['sales_gbp'] = products['sales_units'] / 10000
    products['share_of_merchandise'] = products['sales_units'] / products['sales_units'].sum()
    products['cumulative_share'] = products['share_of_merchandise'].cumsum()
    segments = rfm.groupby('segment').agg(customers=('customer_id', 'size'),
        sales_units=('monetary_units', 'sum'), mean_recency=('recency_days', 'mean'),
        mean_frequency=('frequency', 'mean')).reindex(SEGMENTS, fill_value=0).reset_index()
    segments['sales_gbp'] = segments['sales_units'] / 10000
    segments['customer_share'] = segments['customers'] / segments['customers'].sum()
    segments['sales_share'] = segments['sales_units'] / segments['sales_units'].sum()
    countries = sales.groupby('country', dropna=False).agg(sales_units=('amount_units', 'sum'), orders=('invoice_no', 'nunique')).reset_index()
    countries['sales_gbp'] = countries['sales_units'] / 10000
    countries = countries.sort_values('sales_units', ascending=False)
    return dict(monthly=monthly, orders=orders, products=products, segments=segments, countries=countries)
