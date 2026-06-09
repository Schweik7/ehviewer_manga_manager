"""选项卡: 移动漫画 (分析进度 → 预演 → 执行移动)。"""

from typing import List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QMessageBox,
)

from ...config import DEFAULT_THRESHOLD
from ..helpers import tip


class MoveTab(QWidget):
    request_analyze = pyqtSignal(float)
    request_move = pyqtSignal(list, str, bool, bool)

    def __init__(self):
        super().__init__()
        self._results: List[dict] = []
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(14)

        # ── 目标目录 ──────────────────────────────────────
        dest_box = QGroupBox("目标目录")
        dest_row = QHBoxLayout(dest_box)
        dest_row.setContentsMargins(10, 8, 10, 8)
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("选择或输入本地存储路径…")
        self.dest_edit.setToolTip("漫画将拉取到此目录，每本保存为独立子文件夹")
        browse_btn = QPushButton("浏览…")
        browse_btn.setFixedWidth(72)
        browse_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(self.dest_edit)
        dest_row.addWidget(browse_btn)
        outer.addWidget(dest_box)

        # ── 选项 (2行) ────────────────────────────────────
        opt_box = QGroupBox("选项")
        opt_vlay = QVBoxLayout(opt_box)
        opt_vlay.setContentsMargins(10, 10, 10, 10)
        opt_vlay.setSpacing(10)

        # 第1行: 数值控件
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        thr_lbl = QLabel("阅读进度阈值:")
        thr_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.1, 1.0)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setValue(DEFAULT_THRESHOLD)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setFixedWidth(96)
        _thr_tip = tip(
            "只有阅读完成度 ≥ 此比例的漫画才会进入列表\n" "例如 0.90 = 已读超过 90%"
        )
        self.threshold_spin.setToolTip(_thr_tip.toolTip())

        batch_lbl = QLabel("批次大小:")
        batch_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(0, 9999)
        self.batch_spin.setValue(0)
        self.batch_spin.setSpecialValueText("全部")
        self.batch_spin.setFixedWidth(96)
        _bat_tip = tip(
            "单次执行移动的最多漫画数量\n"
            "0（全部）= 一次性处理所有达标漫画\n"
            "可设较小值分批操作"
        )
        self.batch_spin.setToolTip(_bat_tip.toolTip())

        row1.addWidget(thr_lbl)
        row1.addWidget(_thr_tip)
        row1.addWidget(self.threshold_spin)
        row1.addSpacing(24)
        row1.addWidget(batch_lbl)
        row1.addWidget(_bat_tip)
        row1.addWidget(self.batch_spin)
        row1.addStretch()
        opt_vlay.addLayout(row1)

        # 第2行: 复选框
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self.remove_chk = QCheckBox("移动后删除手机原文件")
        _rm_tip = tip("漫画拉取成功后自动删除手机上\n" "对应的文件夹，释放手机存储")
        self.remove_chk.setToolTip(_rm_tip.toolTip())

        self.sync_chk = QCheckBox("同步更新 EhViewer 数据库")
        _sync_tip = tip(
            "从数据库删除已移走的条目并\n" "推送回手机，App 将不再显示\n" "已移走的漫画"
        )
        self.sync_chk.setToolTip(_sync_tip.toolTip())

        row2.addWidget(self.remove_chk)
        row2.addWidget(_rm_tip)
        row2.addSpacing(24)
        row2.addWidget(self.sync_chk)
        row2.addWidget(_sync_tip)
        row2.addStretch()
        opt_vlay.addLayout(row2)

        outer.addWidget(opt_box)

        # ── 状态摘要 ──────────────────────────────────────
        self.summary_lbl = QLabel("尚未分析 — 请先点击「① 分析」")
        self.summary_lbl.setStyleSheet(
            "color:#999; padding:8px 12px; font-size:11pt;"
            " background:#252525; border-radius:4px;"
        )
        outer.addWidget(self.summary_lbl)

        # ── 操作按钮 ──────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.analyze_btn = QPushButton("① 分析进度")
        self.analyze_btn.setFixedHeight(42)
        self.analyze_btn.setMinimumWidth(110)
        self.analyze_btn.setToolTip(
            "扫描手机上所有漫画的 spiderInfo 文件\n"
            "计算阅读完成度，列出超过阈值的条目"
        )
        self.analyze_btn.clicked.connect(self._on_analyze)

        self.dryrun_btn = QPushButton("② 预演")
        self.dryrun_btn.setFixedHeight(42)
        self.dryrun_btn.setMinimumWidth(110)
        self.dryrun_btn.setEnabled(False)
        self.dryrun_btn.setToolTip(
            "预览将被移动的漫画列表（Dry Run）\n" "不执行任何实际文件操作"
        )
        self.dryrun_btn.clicked.connect(self._on_dryrun)

        self.move_btn = QPushButton("③ 执行移动")
        self.move_btn.setFixedHeight(42)
        self.move_btn.setMinimumWidth(110)
        self.move_btn.setEnabled(False)
        self.move_btn.setToolTip(
            "通过 ADB 将达标漫画拉取到本地目录\n"
            "（根据上方选项决定是否删除原文件和同步数据库）"
        )
        self.move_btn.setStyleSheet(
            "QPushButton{background:#2e5a2e;color:#fff;border-radius:4px;}"
            "QPushButton:hover{background:#3d7a3d;}"
            "QPushButton:disabled{background:#3a3a3a;color:#666;}"
        )
        self.move_btn.clicked.connect(self._on_move)

        btn_row.addWidget(self.analyze_btn)
        btn_row.addWidget(self.dryrun_btn)
        btn_row.addWidget(self.move_btn)
        outer.addLayout(btn_row)

        outer.addStretch()

    # ── 事件 ──────────────────────────────────────────────

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if d:
            self.dest_edit.setText(d)

    def _on_analyze(self):
        self.request_analyze.emit(self.threshold_spin.value())

    def _selected_items(self) -> List[dict]:
        batch = self.batch_spin.value()
        return self._results[:batch] if batch > 0 else self._results

    def _on_dryrun(self):
        if not self._results:
            return
        dest = self.dest_edit.text().strip()
        if not dest:
            QMessageBox.warning(self, "提示", "请先选择目标目录")
            return
        items = self._selected_items()
        lines = [f"[DRY-RUN] 将移动 {len(items)} 个漫画到: {dest}", ""]
        for m in items:
            lines.append(f"  {m['title'][:70]}  ({m['progress']*100:.0f}%)")
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QTextEdit

        dlg = QDialog(self)
        dlg.setWindowTitle("Dry Run 预览")
        dlg.resize(720, 440)
        vl = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setFont(QFont("Consolas", 10))
        te.setPlainText("\n".join(lines))
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        vl.addWidget(te)
        vl.addWidget(bb)
        dlg.exec_()

    def _on_move(self):
        dest = self.dest_edit.text().strip()
        if not dest:
            QMessageBox.warning(self, "提示", "请先选择目标目录")
            return
        if not self._results:
            QMessageBox.warning(self, "提示", "请先执行分析")
            return
        items = self._selected_items()
        if (
            QMessageBox.question(
                self,
                "确认移动",
                f"即将移动 {len(items)} 个漫画到:\n{dest}\n\n"
                f"删除手机原文件: {'是' if self.remove_chk.isChecked() else '否'}\n"
                f"同步数据库:    {'是' if self.sync_chk.isChecked() else '否'}\n\n继续?",
                QMessageBox.Yes | QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        self.request_move.emit(
            items, dest, self.remove_chk.isChecked(), self.sync_chk.isChecked()
        )

    def set_results(self, results: List[dict]):
        self._results = results
        n = len(results)
        if n:
            self.summary_lbl.setText(f"找到 {n} 个达标漫画，可设「批次大小」分批处理")
            self.summary_lbl.setStyleSheet(
                "color:#6fcf6f; padding:6px 8px;"
                " background:#1c2c1c; border-radius:4px;"
            )
        else:
            self.summary_lbl.setText("未找到达到阈值的漫画")
            self.summary_lbl.setStyleSheet(
                "color:#f0c040; padding:6px 8px;"
                " background:#2c2800; border-radius:4px;"
            )
        self.dryrun_btn.setEnabled(n > 0)
        self.move_btn.setEnabled(n > 0)

    def set_busy(self, busy: bool):
        self.analyze_btn.setEnabled(not busy)
        self.dryrun_btn.setEnabled(not busy and bool(self._results))
        self.move_btn.setEnabled(not busy and bool(self._results))
