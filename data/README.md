# 数据来源

Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository.

- 数据页面：https://archive.ics.uci.edu/dataset/352/online+retail
- DOI：https://doi.org/10.24432/C5BW33
- 数据许可：CC BY 4.0
- 原始文件：`Online Retail.xlsx`，541,909 行、8 列
- 时间范围：2010-12-01 至 2011-12-09
- 金额单位：英镑

仓库不包含原始工作簿或全量清洗数据。运行 `run_pipeline.py` 时，如 `data/raw/Online Retail.xlsx` 不存在，程序会从 UCI 官方下载。来源、文件 SHA-256 与分析环境信息保存在 `raw/source_manifest.json`。

`reports/` 中的图表和报告是该数据集的衍生分析，保留上述来源署名。数据许可不自动替代项目源码的许可。
