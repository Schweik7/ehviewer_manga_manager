"""GUI 通用辅助: 背景色设置、帮助提示标签、日志控件。"""

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont, QTextCursor, QColor, QPalette
from PyQt5.QtWidgets import QLabel, QTextEdit


def set_bg(widget, r: int, g: int, b: int):
    """通过 palette 设置控件背景色，不触发 QSS 子控件样式重算。"""
    widget.setAutoFillBackground(True)
    p = widget.palette()
    p.setColor(QPalette.Window, QColor(r, g, b))
    widget.setPalette(p)


def tip(tooltip: str) -> QLabel:
    """生成一个圆形「?」帮助提示小标签。"""
    lbl = QLabel("?")
    lbl.setToolTip(tooltip)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setCursor(Qt.WhatsThisCursor)
    lbl.setFixedSize(17, 17)
    lbl.setStyleSheet(
        "QLabel { color:#7ab3e0; font-weight:bold; font-size:10px;"
        " border:1px solid #5090c0; border-radius:8px; background:#243040; }"
        "QLabel:hover { background:#3a5070; }"
    )
    return lbl


class LogWidget(QTextEdit):
    """带颜色分级的只读日志面板。"""

    COLORS = {"info": "#d8d8d8", "ok": "#6fcf6f", "warn": "#f0c040", "error": "#f07070"}

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 11))
        self.setStyleSheet(
            "background:#1a1a1a; color:#d8d8d8;"
            " border:1px solid #3a3a3a; border-radius:4px;"
        )

    @pyqtSlot(str, str)
    def append_log(self, msg: str, level: str = "info"):
        color = self.COLORS.get(level, self.COLORS["info"])
        esc = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.append(f'<span style="color:{color};">{esc}</span>')
        self.moveCursor(QTextCursor.End)

    def clear_log(self):
        self.clear()
