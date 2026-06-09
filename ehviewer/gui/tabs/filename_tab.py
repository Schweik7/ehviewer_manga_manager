"""选项卡: 文件名检查 (列出含 Windows 非法字符的目录名)。"""

from typing import List

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)


class FilenameTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        top_row = QHBoxLayout()
        self.label = QLabel("点击「检查」扫描数据库中含 Windows 非法字符的目录名")
        self.label.setStyleSheet("color:#aaa;")
        self.check_btn = QPushButton("检查文件名兼容性")
        self.check_btn.setFixedWidth(160)
        self.check_btn.setFixedHeight(36)
        self.check_btn.setToolTip(
            "扫描所有漫画目录名中含有 Windows 非法字符\n"
            '（: * ? " < > |）的条目，移动时自动净化'
        )
        top_row.addWidget(self.label)
        top_row.addStretch()
        top_row.addWidget(self.check_btn)
        lay.addLayout(top_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["GID", "原始目录名", "净化后目录名"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)

    def populate(self, issues: List[dict]):
        self.table.setRowCount(0)
        if not issues:
            self.label.setText("✓ 所有目录名均兼容 Windows，无需净化")
            self.label.setStyleSheet("color:#6fcf6f;")
            return
        self.label.setText(f"发现 {len(issues)} 个需净化的目录名（移动时自动处理）")
        self.label.setStyleSheet("color:#f0c040;")
        for item in issues:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(item["gid"])))
            self.table.setItem(row, 1, QTableWidgetItem(item["original"]))
            self.table.setItem(row, 2, QTableWidgetItem(item["sanitized"]))
