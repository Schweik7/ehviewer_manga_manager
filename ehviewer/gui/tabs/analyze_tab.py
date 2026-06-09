"""选项卡: 分析结果 (达标漫画表格)。"""

from typing import List

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)


class AnalyzeTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        self.info_lbl = QLabel("执行分析后结果显示于此")
        self.info_lbl.setStyleSheet("color:#888;")
        lay.addWidget(self.info_lbl)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["GID", "标题", "进度", "页数", "状态"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)

    def populate(self, results: List[dict]):
        self.table.setRowCount(0)
        n = len(results)
        self.info_lbl.setText(f"共 {n} 个达标漫画" if n else "暂无达标漫画")
        for r in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r["gid"])))
            self.table.setItem(row, 1, QTableWidgetItem(r["title"]))
            self.table.setItem(row, 2, QTableWidgetItem(f"{r['progress']*100:.1f}%"))
            self.table.setItem(
                row, 3, QTableWidgetItem(f"{r['current_page']+1}/{r['total_pages']}")
            )
            self.table.setItem(row, 4, QTableWidgetItem(r["state_text"]))
