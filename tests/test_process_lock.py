"""真实子进程验证残留锁恢复、并发保护和异常终止后的系统自动释放。"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from process_lock import ProjectLock


@unittest.skipUnless(os.name == 'nt', 'Windows 文件锁')
class LockTests(unittest.TestCase):
    def test_old_empty_file_does_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mysql.lock'
            path.touch()
            with ProjectLock(path):
                pass
            with ProjectLock(path):
                self.assertTrue(path.exists())

    def child(self, path):
        code = (f'import sys; sys.path.insert(0, {str(SRC)!r}); '
                'from process_lock import ProjectLock; '
                'lock = ProjectLock(sys.argv[1]).acquire(); '
                'print("locked", flush=True); sys.stdin.read(); lock.release()')
        return subprocess.Popen([sys.executable, '-u', '-c', code, str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)

    def check_child(self, force):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mysql.lock'
            process = self.child(path)
            try:
                self.assertEqual(process.stdout.readline().strip(), b'locked')
                with self.assertRaisesRegex(RuntimeError, '另一个项目任务'):
                    ProjectLock(path).acquire()
                if force:
                    process.terminate()
                process.communicate(timeout=10)
                with ProjectLock(path):
                    pass
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)

    def test_active_owner_blocks_until_normal_exit(self):
        self.check_child(force=False)

    def test_terminated_owner_releases_lock(self):
        self.check_child(force=True)
