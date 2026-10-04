"""用真正的 MySQL 8.0 独立复算，Windows 共享内存连接，不占用现有服务端口。"""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import tempfile

import numpy as np
import pandas as pd

from retail import SOURCE_COLUMNS
from process_lock import ProjectLock


class ProjectMySQL:
    def __init__(self, root):
        self.root = Path(root)
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir(exist_ok=True)
        self.data = self.runtime / 'mysql_data'
        self.name = 'RetailTraining' + __import__('hashlib').sha256(str(root).encode()).hexdigest()[:10]
        self.server = os.getenv('MYSQLD_EXE') or shutil.which('mysqld')
        self.client = os.getenv('MYSQL_EXE') or shutil.which('mysql')
        if not self.server or not self.client:
            raise RuntimeError('未找到 MySQL 8.0。请把 bin 加入 PATH，或设置 MYSQLD_EXE / MYSQL_EXE。')
        self.flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        self.process = None
        self.runtime_alias = self.runtime

    def check_existing_server(self):
        # 强制终止父 Python 后，子 mysqld 可能仍存活。不能据文件锁已释放
        # 就启动第二个实例；按项目专属参数检查，不操作系统 MySQL 服务。
        marker = '--shared-memory-base-name=' + self.name
        command = ("$ErrorActionPreference='Stop'; "
                   "$p = @(Get-CimInstance Win32_Process -Filter \"Name='mysqld.exe'\" | "
                   "Where-Object { $_.CommandLine -and $_.CommandLine.Contains('" + marker + "') }); "
                   "ConvertTo-Json -Compress -InputObject @($p | ForEach-Object { $_.ProcessId })")
        result = subprocess.run(['powershell','-NoProfile','-Command',command],
            capture_output=True, creationflags=self.flags, timeout=20)
        if result.returncode:
            raise RuntimeError('无法检查项目数据库是否仍在运行，已停止启动以避免冲突。')
        pids = json.loads(result.stdout.decode('utf-8-sig'))
        if pids:
            raise RuntimeError(f'项目数据库进程仍在运行（PID: {pids}）。请先结束之前的项目任务；程序不会删除占用标记或强行停止该进程。')

    def prepare_path(self):
        # MySQL Windows 启动参数不能可靠处理中文路径。ASCII 临时目录联接
        # 只提供路径别名；实际数据库、导入文件仍保存在项目 runtime 内。
        if not str(self.runtime).isascii():
            alias = Path(tempfile.gettempdir()) / self.name
            if alias.exists():
                if not alias.samefile(self.runtime):
                    raise RuntimeError('MySQL 临时目录别名已被其他目录占用')
            else:
                quote = lambda s: "'" + str(s).replace("'", "''") + "'"
                command = f"New-Item -ItemType Junction -Path {quote(alias)} -Target {quote(self.runtime)} | Out-Null"
                subprocess.run(['powershell','-NoProfile','-Command',command],check=True,capture_output=True,creationflags=self.flags)
            self.runtime_alias = alias

    def query(self, sql, table=True):
        cmd = [self.client, '--no-defaults', '--protocol=MEMORY',
               '--shared-memory-base-name=' + self.name, '--user=root',
               '--default-character-set=utf8mb4', '--local-infile=1', '--batch', '--raw']
        p = subprocess.run(cmd, input=sql.encode('utf-8'), capture_output=True, creationflags=self.flags)
        if p.returncode:
            raise RuntimeError(p.stderr.decode('utf-8', errors='replace'))
        out = p.stdout.decode('utf-8')
        return pd.read_csv(io.StringIO(out), sep='\t', dtype='string', keep_default_na=False) if table else out

    def __enter__(self):
        if os.name != 'nt':
            raise RuntimeError('项目自动实例脚本面向 Windows；其他系统可在自己的 MySQL 8.0 中运行 sql/ 脚本。')
        self.lock = self.runtime / 'mysql.lock'
        self.guard = ProjectLock(self.lock).acquire()
        try:
            self.check_existing_server()
            self.prepare_path()
            mysql_data_path = self.runtime_alias / 'mysql_data'
            if not (self.data / 'mysql').exists():
                self.data.mkdir(exist_ok=True)
                p = subprocess.run([self.server, '--no-defaults', '--initialize-insecure',
                    '--datadir=' + str(mysql_data_path), '--console'], capture_output=True, creationflags=self.flags)
                (self.runtime / 'mysql_initialize.log').write_bytes(p.stdout + p.stderr)
                if p.returncode:
                    raise RuntimeError('MySQL 初始化失败，见 runtime/mysql_initialize.log')
            self.log = open(self.runtime / 'mysql_server.log', 'wb')
            self.process = subprocess.Popen([self.server, '--no-defaults', '--console', '--standalone',
                '--datadir=' + str(mysql_data_path), '--skip-networking', '--shared-memory',
                '--shared-memory-base-name=' + self.name, '--mysqlx=OFF', '--local-infile=1',
                '--innodb-buffer-pool-size=128M', '--skip-log-bin'],
                stdout=self.log, stderr=subprocess.STDOUT, creationflags=self.flags)
            for _ in range(120):
                if self.process.poll() is not None:
                    raise RuntimeError('MySQL 启动失败，见 runtime/mysql_server.log')
                try:
                    self.query('SELECT 1;', table=False)
                    return self
                except RuntimeError:
                    time.sleep(.5)
            raise TimeoutError('MySQL 启动超时')
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        try:
            if self.process and self.process.poll() is None:
                try:
                    self.query('SHUTDOWN;', table=False)
                    self.process.wait(timeout=30)
                except Exception:
                    self.process.terminate()
                    self.process.wait(timeout=15)
            if hasattr(self, 'log'):
                self.log.close()
            if self.runtime_alias != self.runtime and self.runtime_alias.exists():
                # rmdir 只移除目录联接，不递归删除目标文件。
                os.rmdir(self.runtime_alias)
        finally:
            self.guard.release()


def write_tsv(d, path):
    def escape(x):
        if pd.isna(x):
            return r'\N'
        return str(x).replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        for row in d[['source_row'] + SOURCE_COLUMNS].itertuples(index=False, name=None):
            f.write('\t'.join(escape(x) for x in row) + '\n')


def verify_mysql(root, normalized, audit, sales, rfm, thresholds, tables, reference_date):
    checks = []

    def compare(name, expected, actual, keys, numerics):
        columns = keys + numerics
        e = expected[columns].copy().sort_values(keys).reset_index(drop=True)
        a = actual[columns].copy().sort_values(keys).reset_index(drop=True)
        same = len(e) == len(a) and e[keys].astype(str).equals(a[keys].astype(str))
        max_diff = 0.
        if same:
            for c in numerics:
                ev, av = pd.to_numeric(e[c]).to_numpy(dtype=float), pd.to_numeric(a[c]).to_numpy(dtype=float)
                delta = float(np.max(np.abs(ev-av), initial=0))
                max_diff = max(max_diff, delta)
                same = same and np.array_equal(ev, av)
        checks.append(dict(check=name, pandas_rows=len(e), mysql_rows=len(a), passed=bool(same), max_abs_difference=max_diff))
        if not same:
            e.to_csv(root / 'outputs' / (name + '_expected.csv'), index=False)
            a.to_csv(root / 'outputs' / (name + '_actual.csv'), index=False)

    with ProjectMySQL(root) as db:
        version = db.query('SELECT VERSION() AS version;').iloc[0, 0]
        print('MySQL started: ' + version, flush=True)
        db.query((root / 'sql/01_schema.sql').read_text(encoding='utf-8'), table=False)
        tsv = root / 'runtime/staging.tsv'
        write_tsv(normalized, tsv)
        filename = (db.runtime_alias / 'staging.tsv').as_posix().replace("'", "''")
        db.query(f"USE retail_training; LOAD DATA LOCAL INFILE '{filename}' INTO TABLE staging CHARACTER SET utf8mb4 FIELDS TERMINATED BY '\\t' ESCAPED BY '\\\\' LINES TERMINATED BY '\\n';", table=False)
        db.query((root / 'sql/02_clean.sql').read_text(encoding='utf-8'), table=False)
        prefix = 'USE retail_training; '
        q = lambda sql: db.query(prefix + sql)
        reasons = audit.groupby('reason').size().rename('lines').reset_index()
        compare('cleaning_counts', reasons, q('SELECT reason, COUNT(*) AS `lines` FROM audit GROUP BY reason;'), ['reason'], ['lines'])
        compare('retained_rows', sales[['source_row']].astype({'source_row':str}),
                q('SELECT CAST(source_row AS CHAR) AS source_row FROM sales;'), ['source_row'], [])
        compare('monthly', tables['monthly'], q("SELECT DATE_FORMAT(invoice_date,'%Y-%m') AS month, SUM(amount_units) AS sales_units, COUNT(DISTINCT invoice_no) AS orders, COUNT(DISTINCT customer_id) AS customers, COUNT(*) AS `lines` FROM sales GROUP BY month;"), ['month'], ['sales_units','orders','customers','lines'])
        compare('orders', tables['orders'], q('SELECT invoice_no, SUM(amount_units) AS order_units, COUNT(*) AS `lines` FROM sales GROUP BY invoice_no;'), ['invoice_no'], ['order_units','lines'])
        compare('products', tables['products'], q('SELECT stock_code, SUM(amount_units) AS sales_units, SUM(quantity) AS quantity, COUNT(DISTINCT invoice_no) AS orders FROM sales WHERE is_merchandise=1 GROUP BY stock_code;'), ['stock_code'], ['sales_units','quantity','orders'])
        base = f"SELECT customer_id, DATEDIFF('{reference_date}', DATE(MAX(invoice_date))) AS recency_days, COUNT(DISTINCT invoice_no) AS frequency, SUM(amount_units) AS monetary_units FROM sales WHERE customer_id IS NOT NULL GROUP BY customer_id"
        compare('rfm_base', rfm, q(base + ';'), ['customer_id'], ['recency_days','frequency','monetary_units'])
        # 阈值作为共享业务配置输入；SQL 独立应用阈值和八类映射。
        expr = []
        for col, score in [('recency_days','r_score'),('frequency','f_score'),('monetary_units','m_score')]:
            terms = ' + '.join(f'({col} > {x:.8f})' for x in thresholds[col])
            expr.append(f"{'5 - (' if score == 'r_score' else '1 + ('}{terms}) AS {score}")
        seg = "CASE WHEN m_score>=3 THEN CASE WHEN r_score>=3 THEN IF(f_score>=3,'重要价值客户','重要发展客户') ELSE IF(f_score>=3,'重要保持客户','重要挽留客户') END ELSE CASE WHEN r_score>=3 THEN IF(f_score>=3,'一般价值客户','一般发展客户') ELSE IF(f_score>=3,'一般保持客户','一般挽留客户') END END"
        score_sql = f'WITH base AS ({base}), scored AS (SELECT *, {", ".join(expr)} FROM base) SELECT *, {seg} AS segment FROM scored;'
        (root / 'sql/04_rfm_scoring_generated.sql').write_text('-- 分位点由本次全体可识别客户计算；重跑时自动更新。\nUSE retail_training;\n' + score_sql, encoding='utf-8')
        scored = q(score_sql)
        compare('rfm_scores_segments', rfm, scored, ['customer_id','segment'], ['r_score','f_score','m_score'])
        signed_expected = audit[(audit.reason != 'duplicate') & audit.invoice_date.notna() & audit.quantity.notna() & (audit.unit_price_units > 0)].groupby(audit.invoice_date.dt.strftime('%Y-%m')).amount_units.sum().rename('signed_units').reset_index().rename(columns={'invoice_date':'month'})
        compare('signed_monthly', signed_expected, q("SELECT DATE_FORMAT(invoice_date,'%Y-%m') AS month, SUM(amount_units) AS signed_units FROM audit WHERE reason <> 'duplicate' AND invoice_date IS NOT NULL AND quantity IS NOT NULL AND unit_price_units > 0 GROUP BY month;"), ['month'], ['signed_units'])
    result = {'engine': 'MySQL', 'version': str(version), 'passed': all(x['passed'] for x in checks),
              'checks': checks, 'note': 'SQL 与 pandas 共用类型规范化输入及分位点；独立去重、筛选、聚合、评分。'}
    (root / 'outputs/mysql_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    pd.DataFrame(checks).to_csv(root / 'outputs/tables/mysql_verification.csv', index=False, encoding='utf-8-sig')
    if not result['passed']:
        raise AssertionError('MySQL 与 pandas 存在差异，见 outputs/mysql_verification.json')
    return result


if __name__ == '__main__':
    # 给实训使用者提供已加载数据的 SQL 交互入口，输入 exit 后自动关闭实例。
    project = Path(__file__).resolve().parents[1]
    with ProjectMySQL(project) as database:
        print('项目 MySQL 控制台；可执行 source sql/03_analysis.sql;，输入 exit 退出。', flush=True)
        subprocess.run([database.client, '--no-defaults', '--protocol=MEMORY',
            '--shared-memory-base-name=' + database.name, '--user=root',
            '--default-character-set=utf8mb4', '--database=retail_training'], cwd=project, check=True)
