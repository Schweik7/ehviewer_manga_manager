"""选项卡: 数据库清理 (扫描并清理失效记录)。

典型场景: 导入/恢复旧数据库后, 里面残留大量早已迁移走或删除的漫画记录,
这些记录指向的手机目录已不存在 (失效)。本选项卡一键定位并清理。
"""

from typing import List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)


class CleanTab(QWidget):
    request_scan = pyqtSignal()
    request_clean = pyqtSignal(list, bool)  # gids, push

    def __init__(self):
        super().__init__()
        self._missing: List[dict] = []
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        intro = QLabel(
            "扫描数据库中“已失效”的记录：这些漫画在手机上的目录已不存在\n"
            "（多为之前已迁移到电脑或手动删除），但导入/恢复旧数据库后记录又回来了。"
        )
        intro.setStyleSheet("color:#aaa;")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        top_row = QHBoxLayout()
        self.scan_btn = QPushButton("① 扫描失效记录")
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.setMinimumWidth(150)
        self.scan_btn.setToolTip(
            "一次性列出手机现有目录, 与数据库记录比对,\n"
            "找出指向不存在目录的失效记录 (秒级完成)"
        )
        self.scan_btn.clicked.connect(lambda: self.request_scan.emit())

        self.push_chk = QCheckBox("清理后推送更新到手机")
        self.push_chk.setChecked(True)
        self.push_chk.setToolTip(
            "清理完成后, 把更新后的数据库推送回手机,\n"
            "需在 EhViewer 中: 设置 → 高级 → 导入数据"
        )

        self.clean_btn = QPushButton("② 清理这些记录")
        self.clean_btn.setFixedHeight(36)
        self.clean_btn.setMinimumWidth(150)
        self.clean_btn.setEnabled(False)
        self.clean_btn.setToolTip("从数据库删除上方列出的失效记录")
        self.clean_btn.setStyleSheet(
            "QPushButton{background:#6a3a3a;color:#fff;border-radius:4px;}"
            "QPushButton:hover{background:#8a4a4a;}"
            "QPushButton:disabled{background:#3a3a3a;color:#666;}"
        )
        self.clean_btn.clicked.connect(self._on_clean)

        top_row.addWidget(self.scan_btn)
        top_row.addWidget(self.push_chk)
        top_row.addStretch()
        top_row.addWidget(self.clean_btn)
        lay.addLayout(top_row)

        self.status_lbl = QLabel("尚未扫描 — 请先点击「① 扫描失效记录」")
        self.status_lbl.setStyleSheet(
            "color:#999; padding:6px 10px; background:#252525; border-radius:4px;"
        )
        lay.addWidget(self.status_lbl)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["GID", "标题", "目录名", "状态"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)

    def _on_clean(self):
        if not self._missing:
            return
        gids = [m["gid"] for m in self._missing]
        if (
            QMessageBox.question(
                self,
                "确认清理",
                f"即将从数据库删除 {len(gids)} 条失效记录。\n"
                f"（不会影响手机上现有的漫画文件）\n\n"
                f"清理后推送到手机: {'是' if self.push_chk.isChecked() else '否'}\n\n继续?",
                QMessageBox.Yes | QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        self.request_clean.emit(gids, self.push_chk.isChecked())

    def populate(self, missing: List[dict]):
        self._missing = missing
        self.table.setRowCount(0)
        n = len(missing)
        if n:
            self.status_lbl.setText(f"发现 {n} 条失效记录（手机上目录已不存在）")
            self.status_lbl.setStyleSheet(
                "color:#f0c040; padding:6px 10px; background:#2c2800; border-radius:4px;"
            )
        else:
            self.status_lbl.setText("✓ 没有失效记录，数据库与手机目录一致")
            self.status_lbl.setStyleSheet(
                "color:#6fcf6f; padding:6px 10px; background:#1c2c1c; border-radius:4px;"
            )
        for m in missing:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(m["gid"])))
            self.table.setItem(row, 1, QTableWidgetItem(m["title"]))
            self.table.setItem(row, 2, QTableWidgetItem(m["dirname"]))
            self.table.setItem(row, 3, QTableWidgetItem(m["state_text"]))
        self.clean_btn.setEnabled(n > 0)

    def set_busy(self, busy: bool):
        self.scan_btn.setEnabled(not busy)
        self.clean_btn.setEnabled(not busy and bool(self._missing))
