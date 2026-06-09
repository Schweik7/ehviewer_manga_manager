"""手动选择数据库的对话框: 从手机导出列表挑一个, 或从本地文件加载。"""

from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QDialogButtonBox,
    QFileDialog,
)

from ..config import PUSHED_DB_PREFIX
from ..adb_manager import ADBManager


class DatabaseDialog(QDialog):
    """让用户选择要操作的数据库。

    choice() 返回 ("remote", 文件名) / ("local", 路径) / None(取消)。
    """

    def __init__(self, remote_files: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择数据库")
        self.resize(620, 460)
        self._choice: Optional[Tuple[str, str]] = None

        lay = QVBoxLayout(self)
        info = QLabel(
            "选择要操作的数据库（手机导出目录中的文件，最新在前）。\n"
            "默认即「最新原生导出」；如需操作旧快照或本地文件，可在此手动指定。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#aaa;")
        lay.addWidget(info)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda *_: self._accept_remote())
        default = ADBManager.select_default_database(remote_files)
        for name in remote_files:
            native = not name.startswith(PUSHED_DB_PREFIX)
            tag = "原生导出" if native else "工具清理"
            suffix = "   ← 默认(最新)" if name == default else ""
            it = QListWidgetItem(f"[{tag}]  {name}{suffix}")
            it.setData(Qt.UserRole, name)
            if not native:
                it.setForeground(Qt.gray)
            self.list.addItem(it)
            if name == default:
                self.list.setCurrentItem(it)
        if not remote_files:
            self.list.addItem("（手机导出目录中没有 .db 文件）")
            self.list.setEnabled(False)
        lay.addWidget(self.list)

        row = QHBoxLayout()
        local_btn = QPushButton("从本地文件选择…")
        local_btn.setToolTip("使用电脑上已有的 .db 文件，而不是从手机拉取")
        local_btn.clicked.connect(self._pick_local)
        row.addWidget(local_btn)
        row.addStretch()
        lay.addLayout(row)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("使用所选")
        bb.accepted.connect(self._accept_remote)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _accept_remote(self):
        it = self.list.currentItem()
        name = it.data(Qt.UserRole) if it else None
        if not name:
            return
        self._choice = ("remote", name)
        self.accept()

    def _pick_local(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择本地数据库文件", "", "SQLite 数据库 (*.db);;所有文件 (*.*)"
        )
        if path:
            self._choice = ("local", path)
            self.accept()

    def choice(self) -> Optional[Tuple[str, str]]:
        return self._choice
