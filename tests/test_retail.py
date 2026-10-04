"""验证易出错的边界：缺客户、取消、重复、金额精度、RFM 同分与订单频次。"""
import sys
from pathlib import Path
import unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from retail import normalize, clean, rfm_analysis, segment_scores, SEGMENTS


class RetailTests(unittest.TestCase):
    def raw(self):
        rows=[['100001','12345','A',2,'2011-12-01 10:00',1.005,10001,'UK'],
              ['100001','12346','B',1,'2011-12-01 10:00',2,10001,'UK'],
              ['100002','12345','A',1,'2011-12-02',3,None,'UK'],
              ['C100003','12345','A',-1,'2011-12-03',3,10001,'UK'],
              ['100004','12345','A',0,'2011-12-03',3,10001,'UK'],
              ['100005','12345',None,1,'2011-12-03',0,10001,'UK']]
        rows.append(rows[0].copy())
        return pd.DataFrame(rows,columns=['InvoiceNo','StockCode','Description','Quantity','InvoiceDate','UnitPrice','CustomerID','Country']).assign(InvoiceDate=lambda x:pd.to_datetime(x.InvoiceDate,format='mixed'))

    def test_clean_and_precision(self):
        a,s=clean(normalize(self.raw()))
        self.assertEqual(len(s),3)
        self.assertEqual(int(s.amount_units.sum()),70100)
        self.assertEqual(s.customer_id.isna().sum(),1)
        self.assertEqual(a.reason.value_counts().to_dict(),{'retained':3,'cancelled':1,'nonpositive_quantity':1,'nonpositive_price':1,'duplicate':1})

    def test_rfm_frequency_and_reference(self):
        _,s=clean(normalize(self.raw()))
        r,_=rfm_analysis(s,'2011-12-04')
        self.assertEqual(len(r),1)
        self.assertEqual(r.iloc[0].frequency,1)
        self.assertEqual(r.iloc[0].recency_days,3)
        self.assertEqual(r.iloc[0].monetary_units,40100)

    def test_equal_values_get_equal_scores(self):
        raw=self.raw().iloc[[0]].copy()
        raw=pd.concat([raw.assign(CustomerID=10000+i,InvoiceNo=str(200000+i)) for i in range(20)],ignore_index=True)
        _,s=clean(normalize(raw))
        r,_=rfm_analysis(s,'2011-12-04')
        self.assertTrue((r[['r_score','f_score','m_score']].nunique()==1).all())

    def test_eight_segments(self):
        combos=[(r,f,m) for m in [4,1] for r in [4,1] for f in [4,1]]
        r,f,m=map(pd.Series,zip(*combos))
        self.assertEqual(list(segment_scores(r,f,m)),SEGMENTS)

    def test_missing_description_is_not_deleted(self):
        raw=self.raw().iloc[[0]].copy();raw['Description']=None
        _,s=clean(normalize(raw))
        self.assertEqual(len(s),1)


if __name__=='__main__':unittest.main()
