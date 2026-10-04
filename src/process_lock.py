"""Windows 字节范围锁：由操作系统在进程退出时释放，不以文件存在判断占用。"""
import json
import os
from pathlib import Path


class ProjectLock:
    def __init__(self, path):
        self.path = Path(path)
        self.fd = None

    def acquire(self):
        import msvcrt
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR)
        try:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b' ')
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError('另一个项目任务正在使用数据库，请等待它结束或退出其 SQL 控制台；不要删除锁文件。') from exc
            os.ftruncate(fd, 1)
            os.lseek(fd, 1, os.SEEK_SET)
            os.write(fd, json.dumps({'last_owner_pid': os.getpid()}).encode('ascii'))
            self.fd = fd
        except BaseException:
            os.close(fd)
            raise
        return self

    def release(self):
        if self.fd is not None:
            import msvcrt
            fd, self.fd = self.fd, None
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(fd)
        # 保留占位文件，避免“关闭后删除”与下一个启动任务争抢路径。

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.release()
