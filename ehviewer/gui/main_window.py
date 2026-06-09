"""主窗口: 顶部状态栏 + 左选项卡 + 右日志, 负责调度各后台 Worker。"""

from typing import Optional, List

from PyQt5.QtCore import Qt, QThread, pyqtSlot
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QProgressBar,
    QSplitter,
    QFrame,
    QMessageBox,
    QSizePolicy,
)

from ..manager import MangaManager
from .helpers import set_bg, LogWidget
from .workers import (
    ConnectWorker,
    AnalyzeWorker,
    MoveWorker,
    ScanMissingWorker,
    CleanWorker,
)
from .tabs import MoveTab, AnalyzeTab, FilenameTab, CleanTab

_LBL_RED = "color:#f07070; font-weight:bold; font-size:11pt; background:transparent;"
_LBL_YELLOW = "color:#f0c040; font-weight:bold; font-size:11pt; background:transparent;"
_LBL_GREEN = "color:#6fcf6f; font-weight:bold; font-size:11pt; background:transparent;"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EhViewer 漫画管理工具")
        self.resize(1200, 760)
        self.setMinimumSize(900, 580)
        self._manager: Optional[MangaManager] = None
        self._worker: Optional[QThread] = None
        self._results: List[dict] = []
        self._build_ui()
        self._auto_connect()

    # ── UI 构建 ────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        root_lay.addWidget(self._build_topbar())
        root_lay.addWidget(self._build_body())

    def _build_topbar(self) -> QFrame:
        # ── 顶部状态栏 ── 用 palette 设置背景，避免 QSS 影响子控件颜色
        bar = QFrame()
        bar.setFixedHeight(50)
        bar.setObjectName("topBar")
        # 下边框用 setStyleSheet 只作用于 QFrame 本身，不影响子控件
        bar.setStyleSheet("QFrame#topBar { border-bottom: 1px solid #2e4050; }")
        set_bg(bar, 0x1E, 0x2A, 0x35)

        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(14, 0, 14, 0)
        bar_lay.setSpacing(10)

        self.conn_lbl = QLabel("● 未连接")
        self.conn_lbl.setStyleSheet(_LBL_RED)
        # 防止设备 ID 过长时把右侧按钮挤出视野
        self.conn_lbl.setMaximumWidth(520)
        self.conn_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedSize(150, 14)
        self.progress_bar.setStyleSheet(
            "QProgressBar{border:1px solid #3a5060;border-radius:7px;background:#0f1820;}"
            "QProgressBar::chunk{background:#3a7ab0;border-radius:7px;}"
        )

        self.reconnect_btn = QPushButton("重连")
        self.reconnect_btn.setFixedSize(100, 32)
        self.reconnect_btn.setToolTip("通过 ADB 重新连接手机并拉取最新数据库")
        self.reconnect_btn.clicked.connect(self._auto_connect)

        help_btn = QPushButton("帮助")
        help_btn.setFixedSize(64, 32)
        help_btn.setToolTip("查看使用说明")
        help_btn.clicked.connect(self._show_help)

        # stretch 在 label 和按钮之间 —— 按钮永远贴右侧，有充足空间
        bar_lay.addWidget(self.conn_lbl)
        bar_lay.addStretch()
        bar_lay.addWidget(self.progress_bar)
        bar_lay.addSpacing(6)
        bar_lay.addWidget(self.reconnect_btn)
        bar_lay.addWidget(help_btn)
        return bar

    def _build_body(self) -> QSplitter:
        # ── 主体: 左选项卡 + 右日志 ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle{background:#2e3e4e;}")

        # 左: 选项卡
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.move_tab = MoveTab()
        self.move_tab.request_analyze.connect(self._on_request_analyze)
        self.move_tab.request_move.connect(self._on_request_move)
        self.tabs.addTab(self.move_tab, "  移动漫画  ")

        self.analyze_tab = AnalyzeTab()
        self.tabs.addTab(self.analyze_tab, "  分析结果  ")

        self.filename_tab = FilenameTab()
        self.filename_tab.check_btn.clicked.connect(self._on_check_names)
        self.tabs.addTab(self.filename_tab, "  文件名检查  ")

        self.clean_tab = CleanTab()
        self.clean_tab.request_scan.connect(self._on_request_scan_missing)
        self.clean_tab.request_clean.connect(self._on_request_clean)
        self.tabs.addTab(self.clean_tab, "  数据库清理  ")

        splitter.addWidget(self.tabs)
        splitter.addWidget(self._build_log_panel())

        # 3:2 比例，窗口缩放时按比例分配
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 480])
        return splitter

    def _build_log_panel(self) -> QWidget:
        # 右: 日志 — 用 palette 设置背景，不用 setStyleSheet 避免破坏子控件
        log_panel = QWidget()
        set_bg(log_panel, 0x18, 0x18, 0x18)
        log_lay = QVBoxLayout(log_panel)
        log_lay.setContentsMargins(0, 0, 0, 0)
        log_lay.setSpacing(0)

        log_hdr = QFrame()
        log_hdr.setFixedHeight(42)
        log_hdr.setObjectName("logHdr")
        log_hdr.setStyleSheet("QFrame#logHdr { border-bottom: 1px solid #2e4050; }")
        set_bg(log_hdr, 0x1E, 0x2A, 0x35)

        log_hdr_lay = QHBoxLayout(log_hdr)
        log_hdr_lay.setContentsMargins(12, 0, 8, 0)
        log_hdr_lay.setSpacing(6)
        log_title = QLabel("运行日志")
        log_title.setStyleSheet("font-weight:bold; font-size:10pt;")
        clear_btn = QPushButton("清空")
        clear_btn.setFixedSize(80, 28)
        clear_btn.clicked.connect(lambda: self.log.clear_log())
        log_hdr_lay.addWidget(log_title)
        log_hdr_lay.addStretch()
        log_hdr_lay.addWidget(clear_btn)

        self.log = LogWidget()
        log_lay.addWidget(log_hdr)
        log_lay.addWidget(self.log)
        return log_panel

    # ── 帮助 ────────────────────────────────────────────────

    def _show_help(self):
        QMessageBox.information(
            self,
            "使用说明",
            "【EhViewer 漫画管理工具 使用流程】\n\n"
            "1. 用 USB 连接手机，确保已开启 ADB 调试\n"
            "   程序启动后自动连接并拉取数据库\n\n"
            "2. 在「移动漫画」选项卡中:\n"
            "   · 选择「目标目录」（本地存储路径）\n"
            "   · 调整「阅读进度阈值」（默认 0.90 = 已读 90%）\n"
            "   · 点击「① 分析」扫描所有漫画进度\n"
            "   · 可选「② 预演」确认移动列表\n"
            "   · 点击「③ 执行移动」开始传输\n\n"
            "3. 选项说明:\n"
            "   · 批次大小: 0 = 一次处理全部；>0 = 分批\n"
            "   · 删除手机原文件: 移动成功后删除手机端\n"
            "   · 同步数据库: 清理已移走条目并推回手机\n\n"
            "4. 「文件名检查」可预览含 Windows 非法字符的目录名\n\n"
            "5. 「数据库清理」可扫描并清理失效记录（手机上目录\n"
            "   已不存在的旧记录，常见于导入/恢复旧数据库后）",
        )

    # ── 连接 ────────────────────────────────────────────────

    def _auto_connect(self):
        self._set_busy(True, "正在连接设备并拉取数据库…")
        self.conn_lbl.setText("● 连接中…")
        self.conn_lbl.setStyleSheet(_LBL_YELLOW)
        if self._manager:
            self._manager.cleanup()
            self._manager = None

        w = ConnectWorker()
        w.signals.log.connect(self.log.append_log)
        w.signals.finished.connect(self._on_connected)
        w.signals.error.connect(self._on_connect_error)
        self._worker = w
        w.start()

    @pyqtSlot(object)
    def _on_connected(self, manager):
        self._manager = manager
        self.conn_lbl.setText(f"● 已连接:  {manager.adb.device_id}")
        self.conn_lbl.setStyleSheet(_LBL_GREEN)
        self._set_busy(False)
        self.log.append_log("数据库拉取成功，可以开始操作。", "ok")

    @pyqtSlot(str)
    def _on_connect_error(self, msg):
        self.conn_lbl.setText("● 连接失败")
        self.conn_lbl.setStyleSheet(_LBL_RED)
        self._set_busy(False)
        self.log.append_log(msg, "error")

    # ── 通用 Worker 启动 ────────────────────────────────────

    def _start_worker(self, worker, on_finished):
        """统一连接 log / finished / error 信号并启动 worker。"""
        worker.signals.log.connect(self.log.append_log)
        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(
            lambda e: (self.log.append_log(e, "error"), self._set_busy(False))
        )
        self._worker = worker
        worker.start()

    # ── 分析 ────────────────────────────────────────────────

    @pyqtSlot(float)
    def _on_request_analyze(self, threshold: float):
        if threshold < 0:
            return
        if not self._manager:
            QMessageBox.warning(self, "未连接", "请先连接设备")
            return
        self._set_busy(True, f"正在分析（阈值 {threshold*100:.0f}%）…")
        self.log.append_log(f"\n=== 分析开始  阈值 {threshold*100:.0f}% ===", "info")
        self._start_worker(
            AnalyzeWorker(self._manager, threshold), self._on_analyze_done
        )

    @pyqtSlot(object)
    def _on_analyze_done(self, results):
        self._results = results
        self.move_tab.set_results(results)
        self.analyze_tab.populate(results)
        self._set_busy(False)
        self.log.append_log(f"分析完成: {len(results)} 个达标漫画", "ok")

    # ── 移动 ────────────────────────────────────────────────

    @pyqtSlot(list, str, bool, bool)
    def _on_request_move(self, items, dest, remove, sync):
        if not self._manager:
            return
        self._set_busy(True, f"正在移动 {len(items)} 个漫画…")
        self.log.append_log(f"\n=== 移动开始  {len(items)} 个 → {dest} ===", "info")
        self._start_worker(
            MoveWorker(self._manager, items, dest, remove, sync), self._on_move_done
        )

    @pyqtSlot(object)
    def _on_move_done(self, summary: dict):
        self._set_busy(False)
        moved = len(summary.get("moved", []))
        failed = len(summary.get("failed", []))
        msg = f"移动完成: 成功 {moved}，失败 {failed}"
        self.log.append_log(f"\n{msg}", "ok" if failed == 0 else "warn")
        QMessageBox.information(self, "完成", msg)
        moved_set = set(summary.get("moved", []))
        self._results = [r for r in self._results if r["gid"] not in moved_set]
        self.move_tab.set_results(self._results)
        self.analyze_tab.populate(self._results)

    # ── 文件名检查 ──────────────────────────────────────────

    def _on_check_names(self):
        if not self._manager:
            QMessageBox.warning(self, "未连接", "请先连接设备")
            return
        self.filename_tab.populate(self._manager.preview_filename_issues())

    # ── 数据库清理 (失效记录) ──────────────────────────────

    def _on_request_scan_missing(self):
        if not self._manager:
            QMessageBox.warning(self, "未连接", "请先连接设备")
            return
        self._set_busy(True, "正在扫描失效记录…")
        self.log.append_log("\n=== 扫描失效记录 ===", "info")
        self._start_worker(
            ScanMissingWorker(self._manager), self._on_scan_missing_done
        )

    @pyqtSlot(object)
    def _on_scan_missing_done(self, missing):
        self.clean_tab.populate(missing)
        self._set_busy(False)
        self.log.append_log(f"扫描完成: {len(missing)} 条失效记录", "ok")

    @pyqtSlot(list, bool)
    def _on_request_clean(self, gids, push):
        if not self._manager:
            return
        self._set_busy(True, f"正在清理 {len(gids)} 条记录…")
        self.log.append_log(f"\n=== 清理 {len(gids)} 条失效记录 ===", "info")
        self._start_worker(CleanWorker(self._manager, gids, push), self._on_clean_done)

    @pyqtSlot(object)
    def _on_clean_done(self, summary: dict):
        self._set_busy(False)
        deleted = summary.get("deleted", 0)
        total = summary.get("total", 0)
        pushed = summary.get("pushed", False)
        msg = f"清理完成: 删除 {deleted}/{total} 条记录"
        if pushed:
            msg += "，已推送到手机（请在 EhViewer 导入数据）"
        self.log.append_log(f"\n{msg}", "ok")
        QMessageBox.information(self, "完成", msg)
        # 重新扫描以刷新列表
        self._on_request_scan_missing()

    # ── 辅助 ────────────────────────────────────────────────

    def _set_busy(self, busy: bool, msg: str = ""):
        self.progress_bar.setVisible(busy)
        self.reconnect_btn.setEnabled(not busy)
        self.move_tab.set_busy(busy)
        self.clean_tab.set_busy(busy)
        if msg:
            self.conn_lbl.setText(f"● {msg}")

    def closeEvent(self, event):
        if self._manager:
            self._manager.cleanup()
        event.accept()
