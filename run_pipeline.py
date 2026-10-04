"""项目一键入口：下载、清洗、分析、MySQL 对账、图表与中文报告。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
(ROOT / 'runtime/matplotlib').mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'runtime/matplotlib'))
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
import pandas as pd
from retail import normalize, clean, rfm_analysis, summarize
from mysql_check import verify_mysql
from reporting import make_report

URL = 'https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-mysql', action='store_true', help='只做 pandas 分析；报告明确显示未执行 SQL 核对')
    parser.add_argument('--report-only', action='store_true', help='使用现有结果重新生成图表和报告，不重新分析')
    args = parser.parse_args()
    for d in ['data/raw', 'data/processed', 'outputs/tables', 'outputs/figures', 'runtime']:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    if args.report_only:
        stats = json.loads((ROOT / 'outputs/metrics.json').read_text(encoding='utf-8'))
        verification = json.loads((ROOT / 'outputs/mysql_verification.json').read_text(encoding='utf-8'))
        tables = {p.stem: pd.read_csv(p, dtype={'customer_id':str,'invoice_no':str,'stock_code':str})
                  for p in (ROOT / 'outputs/tables').glob('*.csv')}
        make_report(ROOT, stats, tables, tables['rfm_customers'], verification)
        print('Report regenerated from existing outputs.', flush=True)
        return
    path = ROOT / 'data/raw/Online Retail.xlsx'
    if not path.exists():
        archive = ROOT / 'data/raw/online_retail.zip'
        urllib.request.urlretrieve(URL, archive)
        with zipfile.ZipFile(archive) as z:
            with z.open('Online Retail.xlsx') as src, open(path, 'wb') as dst:
                __import__('shutil').copyfileobj(src, dst)
    print('Reading original Excel...', flush=True)
    raw = pd.read_excel(path, engine='openpyxl')
    manifest = {'source_url': 'https://archive.ics.uci.edu/dataset/352/online+retail',
        'download_url': URL, 'doi': '10.24432/C5BW33', 'license': 'CC BY 4.0',
        'citation': 'Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository.',
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'rows': len(raw), 'columns': list(raw.columns),
        'execution_utc': pd.Timestamp.now(tz='UTC').isoformat(),
        'python': sys.version.split()[0], 'pandas': pd.__version__, 'numpy': np.__version__}
    (ROOT / 'data/raw/source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    d = normalize(raw)
    audit, sales = clean(d)
    reference = (d.invoice_date.max().normalize() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    rfm, thresholds = rfm_analysis(sales, reference)
    tables = summarize(sales, rfm)
    missing = raw.isna().sum().rename('missing_rows').rename_axis('field').reset_index()
    missing['missing_share'] = missing['missing_rows'] / len(raw)
    tables['missing_values'] = missing
    tables['cleaning_audit'] = audit.groupby('reason').agg(lines=('source_row','size'), amount_units=('amount_units','sum')).reset_index()
    tables['cleaning_audit']['share'] = tables['cleaning_audit']['lines'] / len(audit)
    signed = audit[(audit.reason != 'duplicate') & audit.invoice_date.notna() & audit.quantity.notna() & (audit.unit_price_units > 0)]
    signed_monthly = signed.groupby(signed.invoice_date.dt.strftime('%Y-%m')).amount_units.sum().rename('signed_units').reset_index().rename(columns={'invoice_date':'month'})
    tables['monthly'] = tables['monthly'].merge(signed_monthly, on='month')
    tables['monthly']['signed_gbp'] = tables['monthly']['signed_units'] / 10000
    tables['non_merchandise'] = sales[~sales.is_merchandise].groupby('stock_code').agg(lines=('source_row','size'),sales_units=('amount_units','sum')).reset_index()
    tables['non_merchandise']['sales_gbp'] = tables['non_merchandise'].sales_units/10000
    tables['top_orders'] = tables['orders'].nlargest(20, 'order_units')
    tables['score_distribution'] = pd.concat([rfm[c].value_counts().sort_index().rename('customers').rename_axis('score').reset_index().assign(dimension=c) for c in ['r_score','f_score','m_score']], ignore_index=True)
    # 补充查看冲销之后金额变化最大的客户，避免仅凭正向 M 直接营销。
    net_customer = signed.dropna(subset=['customer_id']).groupby('customer_id').amount_units.sum().rename('signed_units')
    tables['customer_amount_sensitivity'] = rfm[['customer_id','monetary_units','segment']].merge(net_customer,on='customer_id',how='left')
    tables['customer_amount_sensitivity']['difference_units'] = tables['customer_amount_sensitivity'].monetary_units - tables['customer_amount_sensitivity'].signed_units
    tables['customer_amount_sensitivity'] = tables['customer_amount_sensitivity'].sort_values('difference_units',ascending=False)
    cutoff = tables['orders'].order_gbp.quantile(.99)
    orders_small = tables['orders'][tables['orders'].order_gbp <= cutoff]
    known = sales[sales.customer_id.notna()]
    top20 = rfm.nlargest(int(np.ceil(len(rfm)*.2)), 'monetary_units')
    stats = dict(raw_rows=len(raw), raw_duplicates=int(raw.duplicated().sum()),
        normalized_duplicates=int(d.duplicated(list(d.columns[1:])).sum()),
        clean_rows=len(sales), orders=sales.invoice_no.nunique(), customers=len(rfm),
        sales_gbp=int(sales.amount_units.sum())/10000,
        signed_gbp=int(signed.amount_units.sum())/10000,
        identified_sales_gbp=int(known.amount_units.sum())/10000,
        unidentified_rows=int(sales.customer_id.isna().sum()),
        unidentified_sales_gbp=int(sales.loc[sales.customer_id.isna(),'amount_units'].sum())/10000,
        merchandise_sales_gbp=int(tables['products'].sales_units.sum())/10000,
        merchandise_codes=len(tables['products']),
        median_order_gbp=float(tables['orders'].order_gbp.median()),
        p99_order_gbp=float(cutoff), aov_under_p99=float(orders_small.order_gbp.mean()),
        high_order_count=int((tables['orders'].order_gbp > cutoff).sum()),
        high_order_sales_share=float(tables['orders'].loc[tables['orders'].order_gbp > cutoff,'order_units'].sum()/sales.amount_units.sum()),
        repeat_customer_share=float((rfm.frequency >= 2).mean()),
        top20_customer_sales_share=float(top20.monetary_units.sum()/rfm.monetary_units.sum()),
        top10_product_share=float(tables['products'].head(10).sales_units.sum()/tables['products'].sales_units.sum()),
        products_for_80pct=int((tables['products'].cumulative_share < .8).sum()+1),
        date_min=str(d.invoice_date.min()), date_max=str(d.invoice_date.max()),
        reference_date=reference, thresholds=thresholds)
    stats['aov_gbp'] = stats['sales_gbp']/stats['orders']
    assert len(audit) == len(raw)
    assert not sales.duplicated(list(d.columns[1:])).any()
    assert sales.amount_units.gt(0).all()
    assert int(tables['monthly'].sales_units.sum()) == int(sales.amount_units.sum())
    assert sales.groupby('invoice_no').customer_id.nunique().le(1).all()
    assert sales.assign(day=sales.invoice_date.dt.normalize()).groupby('invoice_no').day.nunique().le(1).all()
    assert int(tables['monthly'].orders.sum()) == int(sales.invoice_no.nunique())
    assert int(rfm.monetary_units.sum()) == int(known.amount_units.sum())
    assert rfm.customer_id.is_unique and rfm.recency_days.ge(1).all()
    assert rfm[['r_score','f_score','m_score']].isin(range(1,6)).all().all()
    # 保存审计、清洗结果与客户标签，可定位到原 Excel 行号。
    audit.to_csv(ROOT / 'data/processed/row_audit.csv.gz', index=False, compression='gzip', encoding='utf-8-sig')
    sales.to_csv(ROOT / 'data/processed/sales_clean.csv.gz', index=False, compression='gzip', encoding='utf-8-sig')
    rfm.to_csv(ROOT / 'outputs/tables/rfm_customers.csv', index=False, encoding='utf-8-sig')
    for name, table in tables.items():
        table.to_csv(ROOT / f'outputs/tables/{name}.csv', index=False, encoding='utf-8-sig')
    (ROOT / 'outputs/metrics.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Pandas complete: {len(sales):,} sales lines, {len(rfm):,} customers", flush=True)
    if args.skip_mysql:
        verification = {'engine':'MySQL','passed':False,'status':'not_run','checks':[]}
        (ROOT / 'outputs/mysql_verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
        (ROOT / 'outputs/tables/mysql_verification.csv').unlink(missing_ok=True)
    else:
        verification = verify_mysql(ROOT,d,audit,sales,rfm,thresholds,tables,reference)
    make_report(ROOT,stats,tables,rfm,verification)
    print('Completed: outputs/analysis_report.html', flush=True)


if __name__ == '__main__':
    main()
