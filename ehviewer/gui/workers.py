"""后台工作线程: 将耗时的 adb / 数据库操作放到 QThread, 避免阻塞 UI。

各 Worker 通过临时替换 builtins.print 把 manager 的打印转发到 GUI 日志面板,
并按关键字粗略分级 (ok / warn / error / info)。
"""

import os
import traceback
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal, QObject

from ..manager import MangaManager


def _classify(msg: str, ok_kw, err_kw=("失败", "错误", "Error", "error"),
              warn_kw=("警告", "Warning", "warn")) -> str:
    """根据关键字给日志行粗略分级。"""
    if any(k in msg for k in err_kw):
        return "error"
    if any(k in msg for k in warn_kw):
        return "warn"
    if any(k in msg for k in ok_kw):
        return "ok"
    return "info"


class WorkerSignals(QObject):
    log = pyqtSignal(str, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class BaseWorker(QThread):
    """所有工作线程的基类: 提供日志转发与 manager 持有。"""

    # 子类可覆盖: 哪些关键字算 "ok"
    OK_KEYWORDS = ("✓", "完成", "成功", "已拉取", "已连接")

    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self._manager: Optional[MangaManager] = None

    def _log(self, msg: str, level: str = "info"):
        self.signals.log.emit(msg, level)

    def _run_with_log_capture(self, fn):
        """在临时接管 print 的上下文中执行 fn 并返回其结果。"""
        import builtins

        orig = builtins.print

        def gui_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            self._log(msg, _classify(msg, self.OK_KEYWORDS))
            orig(*args, **kwargs)

        builtins.print = gui_print
        try:
            return fn()
        finally:
            builtins.print = orig

    def _cleanup(self):
        if self._manager:
            self._manager.cleanup()


class ConnectWorker(BaseWorker):
    """连接设备并拉取数据库, 成功后把 manager 交回主线程。"""

    def run(self):
        try:
            self._manager = MangaManager()
            ok = self._run_with_log_capture(self._manager.initialize)
            if ok:
                self.signals.finished.emit(self._manager)
            else:
                self.signals.error.emit("初始化失败，请检查 adb 连接")
                self._cleanup()
        except Exception as e:
            self.signals.error.emit(f"连接出错: {e}\n{traceback.format_exc()}")
            self._cleanup()


class AnalyzeWorker(BaseWorker):
    """分析阅读进度, 返回达标漫画列表。"""

    OK_KEYWORDS = ("[达标]",)

    def __init__(self, manager: MangaManager, threshold: float):
        super().__init__()
        self._manager = manager
        self.threshold = threshold

    def run(self):
        try:
            results = self._run_with_log_capture(
                lambda: self._manager.analyze_reading_progress(self.threshold)
            )
            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(f"分析出错: {e}\n{traceback.format_exc()}")


class MoveWorker(BaseWorker):
    """批量迁移漫画到电脑, 可选删除手机原文件并同步数据库。"""

    OK_KEYWORDS = ("已拉取", "成功", "已删除")

    def __init__(self, manager: MangaManager, results: list, dest_dir: str,
                 remove: bool, sync_db: bool):
        super().__init__()
        self._manager = manager
        self.results = results
        self.dest_dir = dest_dir
        self.remove = remove
        self.sync_db = sync_db

    def _do_move(self):
        os.makedirs(self.dest_dir, exist_ok=True)
        moved, failed = [], []
        for manga in self.results:
            ok = self._manager.move_manga_to_pc(
                manga, self.dest_dir, remove_from_phone=self.remove, dry_run=False
            )
            (moved if ok else failed).append(manga["gid"] if ok else manga["title"])

        if self.sync_db and moved:
            print(f"\n正在清理 {len(moved)} 条数据库记录...")
            deleted = self._manager.clean_database_records(moved)
            print(f"已清理 {deleted}/{len(moved)} 条记录")
            self._manager.create_backup_and_push()

        return {"moved": moved, "failed": failed}

    def run(self):
        try:
            summary = self._run_with_log_capture(self._do_move)
            self.signals.finished.emit(summary)
        except Exception as e:
            self.signals.error.emit(f"移动出错: {e}\n{traceback.format_exc()}")


class ScanMissingWorker(BaseWorker):
    """扫描数据库中指向手机上已不存在目录的失效记录。"""

    OK_KEYWORDS = ()

    def __init__(self, manager: MangaManager):
        super().__init__()
        self._manager = manager

    def run(self):
        try:
            missing = self._run_with_log_capture(self._manager.find_missing_manga)
            self.signals.finished.emit(missing)
        except Exception as e:
            self.signals.error.emit(f"扫描出错: {e}\n{traceback.format_exc()}")


class CleanWorker(BaseWorker):
    """清理指定 GID 的数据库记录, 可选推送回手机。"""

    OK_KEYWORDS = ("已删除", "已推送", "完成", "成功")

    def __init__(self, manager: MangaManager, gids: list, push: bool):
        super().__init__()
        self._manager = manager
        self.gids = gids
        self.push = push

    def _do_clean(self):
        deleted = self._manager.clean_database_records(self.gids)
        pushed = False
        if self.push and deleted:
            pushed = self._manager.create_backup_and_push()
        return {"deleted": deleted, "total": len(self.gids), "pushed": pushed}

    def run(self):
        try:
            summary = self._run_with_log_capture(self._do_clean)
            self.signals.finished.emit(summary)
        except Exception as e:
            self.signals.error.emit(f"清理出错: {e}\n{traceback.format_exc()}")
