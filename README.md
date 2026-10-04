# 电商销售与客户分层分析

校内实训项目。使用 UCI Online Retail 原始工作簿，通过 pandas 和真实 MySQL 8.0 独立计算，完成数据清洗、月度销售分析、订单平均金额、商品贡献与 RFM 客户分层。

## 项目展示

**[阅读完整分析报告](reports/analysis_report.md)** · **[详细讲解与答辩准备](docs/项目讲解.md)** · **[SQL 核对结果](reports/mysql_verification.json)**

| 指标 | 结果 |
| --- | ---: |
| 原始明细 | 541,909 行 |
| 有效正向明细 | 524,878 行 |
| 有效订单 | 19,960 张 |
| RFM 客户 | 4,338 人 |
| 有效正向销售额 | £10,642,110.80 |
| 订单平均金额 | £533.17 |

![月度销售趋势](reports/figures/01_monthly_sales.png)

![RFM 客户分层](reports/figures/04_customer_segments.png)

主要发现：重要价值客户占可识别客户的 35.73%，贡献其正向金额的 77.14%；约 21.13% 的标准商品贡献约 80% 的商品正向销售额。2011 年 12 月只有 1–9 日数据，不能直接与完整月份比较。取消记录另做敏感性分析，正向销售额不等于净收入。

仓库包含源码、SQL、测试、来源说明，以及 `reports/` 中的已验证结果快照。原始 Excel、虚拟环境、本地数据库和全量派生明细不上传；运行时可从 UCI 自动下载原始数据并复现。`reports/` 是展示快照，重新运行生成的最新文件位于 `outputs/`。

验证范围：8 项自动测试；MySQL 8.0.46 与 pandas 的 8 项全量核对。Windows 支持完整数据库流程；其他平台可执行 `python run_pipeline.py --skip-mysql` 复现 pandas 分析。

## 先看什么

1. **`outputs/analysis_report.html`**：双击可离线阅读的完整中文图文报告，图表已经嵌入文件。
2. **`docs/项目讲解.md`**：从业务问题到代码实现的详细说明，附答辩问题与简历表达。
3. **`outputs/tables/rfm_customers.csv`**：每位客户的 R、F、M、评分与分层。
4. **`outputs/mysql_verification.json`**：真实 MySQL 执行版本、核对范围与是否一致。
5. **`outputs/figures/`**：五组图表，每组同时提供 PNG 和 SVG，方便用于报告或 PPT。

报告中的金额是**英镑**。主指标为**有效正向销售额**，不是扣除全部退款后的净收入。

## 在这台电脑重新运行

在本文件夹打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

也可以直接运行：

```powershell
.\.venv\Scripts\python.exe run_pipeline.py
```

首次运行读取 54 万余条 Excel 明细，可能需要数分钟；已有原始文件时不再下载。每次重跑会覆盖派生结果和项目专用数据库中的表，原始工作簿不修改。CSV 用带 BOM 的 UTF-8 保存，便于 Excel 查看中文。

如果只需要 pandas 结果：

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --skip-mysql
```

此时报告会明确标记“未执行 MySQL 核对”，不会沿用以前的通过状态。要得到完整验证，请再运行默认命令。

仅修改报告文案或图表后，可用已有结果重新生成展示文件：

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --report-only
```

此命令不重新清洗或验证数据。修改分析口径、清洗规则或原始数据后，应执行完整流程。

## 复制到其他电脑

要求 Python 3.12 或兼容版本、MySQL 8.0（含 mysql / mysqld 可执行文件）。安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_pipeline.py
```

不要复制旧电脑的 `.venv`。如果 MySQL 不在 PATH，配置可执行文件路径：

```powershell
$env:MYSQL_EXE = 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe'
$env:MYSQLD_EXE = 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe'
.\.venv\Scripts\python.exe run_pipeline.py
```

自动数据库管理脚本面向 Windows。它使用 `runtime/mysql_data` 的独立实例，仅启用 Windows 本机共享内存连接，禁用 TCP 与 MySQL X 网络监听，退出时关闭自己启动的进程。不会连接、修改或关闭系统中已有的 MySQL 服务，不要求已有数据库密码。这是本地实训用实例，不作为长期在线数据库服务。可读 SQL 文件在 `sql/`，其他系统可自行导入 MySQL 8.0 后执行。

完整流程运行成功后，可以打开项目自己的 SQL 控制台练习查询：

```powershell
.\.venv\Scripts\python.exe src/mysql_check.py
```

在出现的 `mysql>` 提示符中输入 `source sql/03_analysis.sql;` 可执行分析示例；输入 `exit` 退出后，程序自动关闭本次实例。控制台和全流程不能同时运行，项目锁会阻止并发操作。

为兼容中文项目路径，运行时在 Windows 临时目录创建 ASCII 名称的目录联接，指向本项目 `runtime`；实际数据仍在项目文件夹，退出时仅移除这个临时联接。

`runtime/mysql.lock` 是长期保留的锁占位文件，文件存在不代表任务正在运行，不需要手动删除。系统文件锁会在进程正常退出或被强制终止后自动释放，旧版留下的空锁文件也能直接恢复使用。若强制终止后子 mysqld 仍存活，脚本会提示该项目进程的 PID 并阻止启动第二个实例；请先结束之前的项目任务。初始化或启动错误见 `runtime/mysql_initialize.log` 和 `runtime/mysql_server.log`。不要删除或移动系统 MySQL 数据目录。

## 文件结构

```text
run.ps1                         Windows 一键运行，先测试再分析
run_pipeline.py                 全流程入口
requirements.txt                Python 依赖版本
src/
  retail.py                     类型规范化、清洗、RFM、销售聚合
  mysql_check.py                独立 MySQL 实例、导入及逐项对账
  reporting.py                  PNG/SVG 图表与 HTML/Markdown 报告
sql/
  01_schema.sql                 建库建表
  02_clean.sql                  窗口函数去重与过滤
  03_analysis.sql               月度、商品、RFM 查询示例
  04_rfm_scoring_generated.sql   本次分位点与 SQL 分层（自动生成）
tests/test_retail.py             核心边界测试
tests/test_process_lock.py       并发保护与中断恢复测试
docs/项目讲解.md                 指标、原理、代码、答辩说明
data/raw/
  Online Retail.xlsx            UCI 原始工作簿
  online_retail.zip              来源压缩包
  source_manifest.json          来源、许可、SHA-256、软件版本
data/processed/
  row_audit.csv.gz               全部原始记录及互斥去留原因
  sales_clean.csv.gz             有效正向交易明细
outputs/
  analysis_report.html          单文件离线图文报告
  analysis_report.md            可编辑 Markdown 报告
  metrics.json                  项目关键指标与评分阈值
  mysql_verification.json       数据库核对证据
  tables/                       CSV 结果表
  figures/                      五组 PNG / SVG 图
runtime/                        项目数据库、日志、临时导入与绘图缓存
```

## 输出表说明

| 文件 | 用途 |
| --- | --- |
| monthly.csv | 月度正向销售、订单数、订单均值、含冲销金额、完整月标记 |
| orders.csv / top_orders.csv | 全部订单金额与大额订单复核 |
| products.csv | 标准商品销售额、销售占比及累计贡献 |
| non_merchandise.csv | 非标准商品代码的正向收费单列 |
| countries.csv | 按国家汇总销售额和订单数 |
| missing_values.csv | 原始字段缺失行数与比例 |
| cleaning_audit.csv | 互斥的清洗去留原因及行数 |
| rfm_customers.csv | 客户基础 RFM、1–5 分评分和八类分层 |
| segments.csv | 八类客户人数、销售贡献、平均 R/F |
| score_distribution.csv | 各评分档位人数，用来观察并列值影响 |
| customer_amount_sensitivity.csv | 客户正向金额与含冲销金额的差异 |
| mysql_verification.csv | SQL/pandas 各项核对结果 |

所有 `_units` 列均为万分之一英镑整数，除以 10,000 得英镑；`_gbp` 为英镑；`_share` 为 0–1 比例。`mom_sales` 为完整月销售环比，首月和不完整末月为空。RFM 详解见 `docs/项目讲解.md`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖：保留缺客户交易、取消/数量/价格过滤、去重、三位小数单价、订单级购买频次、日期基准、同值同分、八类分层全覆盖、缺描述不误删。全量运行还执行金额守恒、源行守恒、评分范围等断言。MySQL 从规范化原始输入独立清洗，核对全量源行与聚合结果；并非仅比较一个总数。

锁机制另有真实子进程测试：旧空锁文件可恢复、正在运行的任务阻止并发、持锁进程被强制终止后可重新获取锁。

## 数据来源与许可

Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 。

数据页：https://archive.ics.uci.edu/dataset/352/online+retail

数据许可：CC BY 4.0。分享原始数据或衍生分析时保留来源与署名。数据描述的是 2010–2011 年历史交易，不能代表当今电商市场。
