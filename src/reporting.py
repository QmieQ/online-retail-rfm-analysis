"""可离线阅读的中文 HTML / Markdown 报告与可分享的 PNG / SVG 图表。"""
import base64
from html import escape
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker
import numpy as np


def setup_style():
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ['Microsoft YaHei','SimHei','Noto Sans CJK SC','SimSun'] if f in available),'DejaVu Sans')
    plt.rcParams.update({'font.family':font, 'axes.unicode_minus':False,
        'font.size':11, 'axes.titlesize':17, 'axes.titleweight':'bold',
        'axes.spines.top':False, 'axes.spines.right':False,
        'axes.edgecolor':'#ccd5df', 'text.color':'#182d41', 'axes.labelcolor':'#40576a',
        'xtick.color':'#40576a','ytick.color':'#40576a','figure.facecolor':'white',
        'axes.facecolor':'white','savefig.facecolor':'white'})


def charts(root, s, tables, rfm):
    setup_style()
    out = root / 'outputs/figures'
    def save(fig, name):
        fig.savefig(out / f'{name}.png',dpi=150,bbox_inches='tight')
        fig.savefig(out / f'{name}.svg',bbox_inches='tight')
        plt.close(fig)

    m = tables['monthly']
    x = np.arange(len(m))
    fig, ax = plt.subplots(figsize=(12,5.5), layout='constrained')
    ax.bar(x,m.sales_gbp/10000,color=['#1b887d' if c else '#dba54b' for c in m.complete_month],width=.6,label='有效正向销售')
    ax.plot(x,m.signed_gbp/10000,color='#334d75',marker='o',label='含冲销的有符号交易金额')
    ax.set(title='月度销售趋势',ylabel='金额（万英镑）',xticks=x,xticklabels=m.month)
    ax.tick_params(axis='x',rotation=40)
    ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    ax.legend(frameon=False,loc='upper left')
    ax.annotate('仅 12 月 1–9 日',xy=(12,float(m.sales_gbp.iloc[-1]/10000)),xytext=(9.5,120),arrowprops={'arrowstyle':'->','color':'#a66b15'},color='#a66b15')
    save(fig,'01_monthly_sales')

    fig, axes = plt.subplots(1,2,figsize=(12,5),layout='constrained')
    axes[0].plot(x,m.aov_gbp,color='#1b887d',marker='o')
    axes[0].set(title='月度订单平均金额',ylabel='英镑 / 订单',xticks=x,xticklabels=m.month)
    axes[0].tick_params(axis='x',rotation=55)
    vals = [s['aov_gbp'],s['median_order_gbp'],s['aov_under_p99']]
    bars = axes[1].bar(['全部订单均值','全部订单中位数','剔除最高约 1% 后均值'],vals,color=['#1b887d','#7086a6','#dba54b'])
    axes[1].bar_label(bars,fmt='£%.2f',padding=5)
    axes[1].set(title='大额订单对均值的影响',ylabel='英镑 / 订单',ylim=(0,max(vals)*1.2))
    axes[1].tick_params(axis='x',labelsize=10)
    save(fig,'02_order_value')

    p = tables['products']
    top = p.head(10).iloc[::-1]
    fig, axes = plt.subplots(1,2,figsize=(13,6),layout='constrained')
    bars=axes[0].barh(top.stock_code.astype(str),top.sales_gbp/10000,color='#1b887d')
    axes[0].bar_label(bars,fmt='%.1f',padding=4)
    axes[0].set(title='销售额前十商品',xlabel='正向销售额（万英镑）',ylabel='StockCode')
    axes[0].set_xlim(0,float(top.sales_gbp.max()/10000)*1.18)
    xx=np.arange(1,len(p)+1)/len(p)
    axes[1].plot(xx,p.cumulative_share,color='#334d75',linewidth=2)
    axes[1].axhline(.8,color='#dba54b',linestyle='--')
    axes[1].axvline(s['products_for_80pct']/len(p),color='#dba54b',linestyle='--')
    axes[1].set(title='商品销售贡献累计曲线',xlabel='按销售额降序排列的商品占比',ylabel='累计销售额占比',xlim=(0,1),ylim=(0,1.02))
    axes[1].xaxis.set_major_formatter(ticker.PercentFormatter(1)); axes[1].yaxis.set_major_formatter(ticker.PercentFormatter(1))
    save(fig,'03_product_contribution')

    g=tables['segments'].iloc[::-1]
    y=np.arange(len(g))
    fig,ax=plt.subplots(figsize=(12,6),layout='constrained')
    ax.barh(y-.18,g.customer_share,height=.34,color='#7086a6',label='客户占比')
    ax.barh(y+.18,g.sales_share,height=.34,color='#1b887d',label='正向金额占比')
    ax.set(yticks=y,yticklabels=g.segment,title='RFM 八类客户：人数与销售贡献',xlabel='占全部可识别客户 / 其正向金额的比例')
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(1));ax.legend(frameon=False)
    save(fig,'04_customer_segments')

    heat=rfm.pivot_table(index='r_score',columns='f_score',values='customer_id',aggfunc='count',fill_value=0).reindex(index=range(1,6),columns=range(1,6),fill_value=0)
    fig,ax=plt.subplots(figsize=(7,6),layout='constrained')
    im=ax.imshow(heat.values,origin='lower',cmap='YlGnBu')
    for i in range(5):
        for j in range(5):
            v=heat.iloc[i,j]
            ax.text(j,i,str(v),ha='center',va='center',color='white' if v>heat.values.max()*.5 else '#182d41')
    ax.set(xticks=range(5),xticklabels=range(1,6),yticks=range(5),yticklabels=range(1,6),xlabel='F 分：购买频次从低到高',ylabel='R 分：购买从久远到近期',title='客户活跃度与购买频次分布')
    fig.colorbar(im,ax=ax,label='客户数')
    save(fig,'05_rfm_heatmap')


def make_report(root, s, tables, rfm, v):
    charts(root,s,tables,rfm)
    gbp=lambda n:f'£{n:,.2f}'
    pct=lambda n:f'{n:.2%}'
    clean=tables['cleaning_audit']
    reason_names={'duplicate':'规范化后重复行','invalid_required':'必要字段无效','cancelled':'C 开头取消记录','nonpositive_quantity':'非取消且数量≤0','nonpositive_price':'此前未剔除且单价≤0','retained':'保留的有效正向明细'}
    clean=clean.assign(reason=clean.reason.map(reason_names))
    complete=tables['monthly'][tables['monthly'].complete_month]
    peak=complete.loc[complete.sales_units.idxmax()]
    group=tables['segments'].set_index('segment').loc['重要价值客户']
    sensitivity=tables['customer_amount_sensitivity'].copy()
    sensitivity['positive_gbp']=sensitivity.monetary_units/10000
    sensitivity['signed_gbp']=sensitivity.signed_units/10000
    sensitive=sensitivity.iloc[0]
    known_share=s['identified_sales_gbp']/s['sales_gbp']
    check_status=f"MySQL {v.get('version','')} 已实际执行，{len(v['checks'])} 项核对全部一致。" if v['passed'] else '本次未执行 MySQL 核对；不能宣称 SQL 验证通过。'
    thresholds=s['thresholds']
    threshold_text='；'.join(f"{name}：{', '.join(f'{n/div:g}' for n in thresholds[key])}" for key,name,div in [('recency_days','R（天）',1),('frequency','F（单）',1),('monetary_units','M（英镑）',10000)])
    sections=[]
    def add(title,text,table=None,figure=None):
        sections.append((title,text,table,figure))
    add('1. 项目结论',f"本项目读取 {s['raw_rows']:,} 行原始明细，保留 {s['clean_rows']:,} 行有效正向交易，覆盖 {s['orders']:,} 张订单。有效正向销售额为 {gbp(s['sales_gbp'])}，订单平均金额为 {gbp(s['aov_gbp'])}，可用于 RFM 的客户有 {s['customers']:,} 人。\n\n完整月份中，{peak['month']} 的正向销售额最高，为 {gbp(peak['sales_gbp'])}。重要价值客户占 {pct(group.customer_share)}，贡献可识别客户正向金额的 {pct(group.sales_share)}。这些结果可用于选择优先分析和服务的客群，尚不代表营销措施已经产生效果。")
    add('2. 数据来源与适用范围',f"来源：UCI Online Retail，Chen, D. (2015)，DOI 10.24432/C5BW33，CC BY 4.0。数据记录英国一家无实体门店零售商的交易，包含批发客户。来源页：https://archive.ics.uci.edu/dataset/352/online+retail 。\n\n本地文件实际时间范围：{s['date_min']} 至 {s['date_max']}。本次 RFM 基准日为 {s['reference_date']}，与当前日期无关。金额单位为英镑，不能当成人民币。UCI 页面缺失值标注与实际文件不完全一致，以下按工作簿实测结果处理。2011 年 12 月仅覆盖 1–9 日，不计算完整月环比。",tables['missing_values'])
    add('3. 清洗规则与审计',f"一行代表发票中的一条明细，一张订单可有多行。先规范字符串、日期、数量和客户编号，再按原始八字段去重，保留第一次出现的源行。原始完全重复行有 {s['raw_duplicates']:,} 行，规范化后重复行有 {s['normalized_duplicates']:,} 行。重复行不能仅按订单号去重，否则会丢失同一订单中的其他商品。\n\n剔除原因按顺序互斥归类：重复 → 必要字段无效 → C 开头取消 → 数量≤0 → 单价≤0。表中各类行数相加等于原始总行数。描述或国家缺失不自动删除交易；保留源行号，便于核查。完全相同的行也可能是真实重复购买，本项目按数据清洗假设去重，不宣称已还原订单后台。\n\n缺客户编号的有效交易保留 {s['unidentified_rows']:,} 行，金额 {gbp(s['unidentified_sales_gbp'])}；它们用于整体销售分析，不填补或猜测客户身份，因此不进入 RFM。识别到客户的正向金额覆盖率为 {pct(known_share)}。",clean[['reason','lines','share']])
    add('4. 金额与订单口径',f"有效正向销售额 = 非取消、数量>0、单价>0 的去重明细金额之和；明细金额 = Quantity × UnitPrice。主口径包含运费、手续费等正向收费行，因此不能等同于净商品收入。订单数 = 有效明细中 InvoiceNo 去重数；订单平均金额 = 正向销售额 ÷ 订单数，不是每条商品明细的均价。\n\n金额内部使用万分之一英镑的整数，保留原始价格的小数精度；汇总完再显示两位小数。MySQL 也采用相同整数单位，因此金额核对要求完全相等。\n\n辅助口径“含冲销的有符号交易金额”为 {gbp(s['signed_gbp'])}：保留去重后单价>0、数量及日期有效的正负数量记录，按记录日期汇总。它没有逐一匹配原订单，不是审计后的会计净收入，正向口径与它的差值也不是已验证的退货率。零价、负价和其他异常未纳入该辅助口径。")
    add('5. 月度销售与订单金额',f"最高完整月是 {peak['month']}，正向销售额 {gbp(peak['sales_gbp'])}，订单数 {int(peak['orders']):,}。可观察到年末月份交易活跃，但仅有约一年数据，无法确认长期季节性或增长原因；数据没有广告、促销和流量字段，不能把变化直接归因于运营活动。\n\n应同时观察金额和订单数：金额增长可能来自订单增加，也可能来自大额订单。2011-12 的柱形仅表示已观察到的九天交易，不解释为销售崩塌。",tables['monthly'][['month','sales_gbp','orders','aov_gbp','signed_gbp','complete_month']],'01_monthly_sales')
    add('6. 大额订单敏感性',f"全体订单均值为 {gbp(s['aov_gbp'])}，中位数为 {gbp(s['median_order_gbp'])}。99% 分位金额为 {gbp(s['p99_order_gbp'])}，超过此阈值的 {s['high_order_count']:,} 张订单贡献 {pct(s['high_order_sales_share'])} 的正向金额。仅作敏感性比较时，排除这些订单后的均值为 {gbp(s['aov_under_p99'])}。\n\n主分析保留大额订单，因为来源包含批发客户，大额不自动等于错误。上线运营前应结合取消/冲销和订单后台复核这些交易，尤其不要仅凭一次大额正向购买就发放高成本权益。",tables['top_orders'][['invoice_no','order_date','order_gbp']].head(10),'02_order_value')
    add('6.1 冲销对客户金额的影响',f"金额差异最大的客户 {sensitive['customer_id']}，正向累计金额为 {gbp(sensitive['positive_gbp'])}，按本辅助口径计入冲销后为 {gbp(sensitive['signed_gbp'])}。该客户基于正向口径被标记为“{sensitive['segment']}”，因此这个标签不能直接等同于真实净贡献高。下表给出差异最大的五位客户，供订单复核。",sensitivity[['customer_id','segment','positive_gbp','signed_gbp']].head(5))
    add('7. 商品贡献',f"商品以 StockCode 聚合，描述仅作展示，使用最后一个非空描述。商品排名将“5 位数字 + 可选英文字母”的代码作为标准商品代理规则，单列 POST、DOT、M 等非标准收费代码；这是一项可复现的规则，不能替代正式商品主数据。商品正向金额合计 {gbp(s['merchandise_sales_gbp'])}，不同商品代码 {s['merchandise_codes']:,} 个。\n\n前十商品贡献商品正向金额的 {pct(s['top10_product_share'])}；累计贡献达到 80% 需要 {s['products_for_80pct']:,} 个商品，占商品种类的 {pct(s['products_for_80pct']/s['merchandise_codes'])}。据此可优先复核重点商品供货、库存和退货情况；本数据没有成本和库存，不能判断利润或断货损失。\n\n商品 23843 的正向排名很高，但原始记录存在相应大额取消，不能据此直接认定它是稳定热销商品。商品贡献是正向交易描述，应结合冲销明细与订单频次复核。",tables['products'][['stock_code','description','sales_gbp','share_of_merchandise']].head(10),'03_product_contribution')
    add('8. RFM 如何计算',f"R（Recency）= 基准日 {s['reference_date']} 减去客户最后一次有效正向购买日期，按日历天计算，越小越活跃。F（Frequency）= 观察期内不同有效订单数，越大代表购买次数越多。M（Monetary）= 观察期内累计有效正向金额，越大代表购买金额越高。\n\n每个维度以全体可识别客户的 20%、40%、60%、80% 分位点评分 1–5。阈值为：{threshold_text}。原值等于阈值时放入较低数值档，R 再反向评分。因此 R 越近分越高，F/M 越大分越高。频次大量并列时，各档客户数不相等，甚至可能出现空档；不使用按行号强行拆分并列值的办法。\n\n每个维度评分≥3记为高，否则为低，组成八种互斥且完整的客户类型。M 高为“重要”，M 低为“一般”；R高F高为“价值”，R高F低为“发展”，R低F高为“保持”，R低F低为“挽留”。标签是本项目的运营规则，不是预测模型，也不能保证客户真实流失或未来购买。",tables['segments'][['segment','customers','customer_share','sales_gbp','sales_share','mean_recency','mean_frequency']],'04_customer_segments')
    add('9. 分层运营建议',f"重要价值客户：优先提供稳定供货与服务，验证复购是否提升。重要发展客户：核实大额新订单及冲销后，再通过商品组合引导第二次购买。重要保持/挽留客户：先检查距上次购买时间和历史冲销，按历史贡献分批召回。一般发展客户：使用低成本的新客引导；一般低活跃客户：控制触达成本，保留对照组。\n\n这些是待验证建议。建议在每类客户内部随机分组，比较 30 天复购率、每客户净贡献、优惠成本与退订率；正式投放还需补充可触达渠道与授权、毛利、取消匹配、库存等数据。本项目没有投放实验，不能宣称提升了销售额或转化率。\n\n观察期内至少两次购买的客户占 {pct(s['repeat_customer_share'])}，这只是窗口内复购客户占比，不是完整生命周期留存率。按正向金额排序的前 20% 客户贡献 {pct(s['top20_customer_sales_share'])} 的可识别客户金额。RFM 未校正新客户入场时间，不能把新客的低频直接解释为低忠诚。",figure='05_rfm_heatmap')
    add('10. SQL 与 pandas 交叉验证',check_status + '\n\n两套实现从同一份仅做类型规范化的原始表出发，分别去重、筛选并汇总。核对包括：清洗原因计数、每一条保留源行、全部月份、每一张订单、全部标准商品、每一位客户的 R/F/M、评分与分层，以及含冲销的月度金额。不是只对总金额。\n\n评分分位点是共享业务配置，SQL 独立套用评分与八类规则；类型规范化与阈值计算本身没有第二套独立实现。通过代表性边界单元测试与数据断言补充验证。所有金额均核对到内部整数单位，人数和标签要求完全相等。独立 MySQL 实例只通过本机共享内存连接，运行后自动关闭。',__import__('pandas').DataFrame(v['checks']) if v['checks'] else None)
    add('11. 局限与后续工作','取消记录是负向事件，主分析没有按原订单逐笔抵销，需结合 customer_amount_sensitivity.csv 检查大额客户。部分大额正向金额可能随后被完全冲销。销售额不等于利润，客户价值标签也不等于客户终身价值。\n\n本项目展示历史快照，后续验证应按时间切分，用前期交易产生标签，再用后期交易验证复购或金额，避免用未来信息解释过去。还可补充客户首购月份、同龄客群比较、退货匹配、毛利和促销实验。所有运营建议均应经过数据补充与实际验证。')

    # 单文件报告内嵌 PNG，可复制到任何设备后离线阅读。
    html_sections=[];md=['# 电商销售与客户分层分析\n\n校内实训项目 · pandas / MySQL / RFM\n']
    def table_md(df):
        def val(x):
            if isinstance(x,(float,np.floating)):return f'{x:,.4f}'
            return str(x).replace('|','/')
        return '| '+' | '.join(df.columns)+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(val(x) for x in row)+' |' for row in df.itertuples(index=False,name=None))
    def readable(df):
        df=df.copy()
        labels={'field':'原始字段','missing_rows':'缺失行数','missing_share':'缺失比例',
            'reason':'处理结果','lines':'明细行数','share':'占原始行数',
            'month':'月份','sales_gbp':'正向金额（英镑）','orders':'订单数',
            'aov_gbp':'每单均值（英镑）','signed_gbp':'含冲销金额（英镑）',
            'complete_month':'完整月份','invoice_no':'订单号','order_date':'订单日期',
            'order_gbp':'订单金额（英镑）','stock_code':'商品代码','description':'商品描述',
            'share_of_merchandise':'占商品金额','segment':'客户类型','customers':'客户数',
            'customer_share':'客户占比','sales_share':'金额占比','mean_recency':'平均 R（天）',
            'mean_frequency':'平均 F（单）','customer_id':'客户编号','positive_gbp':'正向金额（英镑）',
            'check':'核对内容','pandas_rows':'pandas 行数','mysql_rows':'MySQL 行数',
            'passed':'一致','max_abs_difference':'最大绝对差'}
        for c in df.columns:
            if c.endswith('_share') or c in ['share','share_of_merchandise']:
                df[c]=df[c].map(lambda x:f'{x:.2%}')
            elif c.endswith('_gbp') or c.startswith('mean_'):
                df[c]=df[c].map(lambda x:f'{x:,.2f}')
            elif c in ['complete_month','passed']:
                df[c]=df[c].map({True:'是',False:'否'})
        if 'check' in df:
            df['check']=df['check'].replace({'cleaning_counts':'清洗原因计数','retained_rows':'全部保留源行','monthly':'全部月度指标','orders':'全部订单','products':'全部商品','rfm_base':'全部客户 RFM','rfm_scores_segments':'全部客户评分及标签','signed_monthly':'含冲销月度金额'})
        return df.rename(columns=labels)
    for i,(title,text,table,figure) in enumerate(sections):
        content=''.join('<p>'+escape(p)+'</p>' for p in text.split('\n\n'))
        md += ['\n## '+title+'\n',text+'\n']
        if figure:
            img=base64.b64encode((root/f'outputs/figures/{figure}.png').read_bytes()).decode()
            content+=f'<img src="data:image/png;base64,{img}" alt="{escape(title)}">'
            md += [f'\n![{title}](figures/{figure}.png)\n']
        if table is not None and not table.empty:
            table=readable(table)
            content+='<div class="table-wrap">'+table.to_html(index=False,border=0,classes='data',float_format=lambda x:f'{x:,.4f}')+'</div>'
            md += ['\n'+table_md(table)+'\n']
        html_sections.append(f'<section id="s{i}"><h2>{escape(title)}</h2>{content}</section>')
    nav=''.join(f'<a href="#s{i}">{escape(z[0])}</a>' for i,z in enumerate(sections))
    cards=''.join(f'<div class="metric"><span>{label}</span><strong>{value}</strong></div>' for label,value in [('正向销售额',gbp(s['sales_gbp'])),('有效订单',f"{s['orders']:,}"),('订单平均金额',gbp(s['aov_gbp'])),('RFM 客户',f"{s['customers']:,}")])
    style='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f3f5f8;color:#23394b;font:16px/1.85 "Microsoft YaHei",sans-serif}header{padding:54px max(6vw,24px);background:#132d42;color:white}header .eyebrow{color:#8cd9ca;font-size:14px;letter-spacing:2px}h1{font-size:36px;margin:12px 0}header p{color:#ccdae7}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:30px}.metric{border-top:2px solid #57bda9;padding-top:12px}.metric span{display:block;font-size:13px;color:#bacddd}.metric strong{display:block;font-size:26px;font-weight:600}main{max-width:1160px;margin:auto;padding:26px}nav{display:flex;flex-wrap:wrap;gap:8px 20px;padding:12px 0 26px}a{color:#177d71;text-decoration:none}section{background:white;margin:0 0 22px;padding:28px 34px;border:1px solid #e0e6ed;border-radius:8px}h2{font-size:23px;margin:0 0 16px}p{margin:0 0 16px}img{width:100%;height:auto;display:block;margin:20px 0}.table-wrap{overflow:auto;margin-top:20px}table{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}th{background:#eaf2f4;text-align:left;padding:10px}td{border-bottom:1px solid #e3e9ef;padding:9px;text-align:right}td:first-child{text-align:left}footer{color:#667c8d;padding:10px 30px 36px;font-size:13px}@media(max-width:760px){.metrics{grid-template-columns:repeat(2,1fr)}h1{font-size:27px}.metric strong{font-size:22px}section{padding:22px 18px}main{padding:16px}}@media print{body{background:white}header{background:white;color:#132d42;padding:20px}header p,.metric span{color:#40576a}nav{display:none}section{break-inside:avoid;border:0;padding:12px}main{padding:0}img{max-height:620px;object-fit:contain}}'''
    html=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>电商销售与客户分层分析</title><style>{style}</style><header><div class="eyebrow">UCI ONLINE RETAIL · 校内实训项目</div><h1>电商销售与客户分层分析</h1><p>2010.12.01—2011.12.09 · 金额：英镑 · RFM 基准日：{s["reference_date"]}</p><div class="metrics">{cards}</div></header><main><nav>{nav}</nav>{"".join(html_sections)}</main><footer>数据：Chen, D. (2015). Online Retail. UCI Machine Learning Repository. DOI: 10.24432/C5BW33. CC BY 4.0。<br>本报告由项目代码从原始工作簿自动生成；详细复现与答辩说明见 README.md 和 docs/项目讲解.md。</footer></html>'
    (root/'outputs/analysis_report.html').write_text(html,encoding='utf-8')
    (root/'outputs/analysis_report.md').write_text('\n'.join(md),encoding='utf-8')
