"""EhViewer 漫画管理工具 - PyQt5 图形界面包。

对外只暴露 run_gui(); 其余模块按职责拆分:
  - helpers.py     通用控件辅助 (背景色、提示标签、日志面板)
  - workers.py     后台 QThread 工作线程
  - tabs/          各功能选项卡
  - main_window.py 主窗口与调度逻辑
"""

import sys

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QColor, QPalette

from .main_window import MainWindow

__all__ = ["run_gui", "MainWindow"]


def _dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(38, 38, 38))
    pal.setColor(QPalette.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.Base, QColor(26, 26, 26))
    pal.setColor(QPalette.AlternateBase, QColor(34, 34, 34))
    pal.setColor(QPalette.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.Button, QColor(52, 52, 52))
    pal.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    pal.setColor(QPalette.Highlight, QColor(50, 100, 170))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipBase, QColor(30, 45, 60))
    pal.setColor(QPalette.ToolTipText, QColor(210, 225, 240))
    pal.setColor(QPalette.Mid, QColor(55, 55, 55))
    pal.setColor(QPalette.Dark, QColor(20, 20, 20))
    return pal


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 11))
    app.setPalette(_dark_palette())

    win = MainWindow()
    win.show()
    return app.exec_()
