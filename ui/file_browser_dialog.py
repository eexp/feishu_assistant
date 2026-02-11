"""通用云盘文件浏览对话框 - 供表格/多维表格 Tab 复用"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMessageBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QThread, Signal


FILE_TYPE_ICONS = {
    "doc": "📝",
    "docx": "📝",
    "sheet": "📊",
    "bitable": "📋",
    "mindnote": "🧠",
    "folder": "📁",
    "file": "📄",
    "slides": "📽️",
    "wiki": "📚",
}


class _LoadWorker(QThread):
    """异步加载文件列表"""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, drive_api, folder_token):
        super().__init__()
        self.drive_api = drive_api
        self.folder_token = folder_token

    def run(self):
        try:
            all_files = []
            page_token = ""
            while True:
                result = self.drive_api.list_files(
                    folder_token=self.folder_token,
                    page_token=page_token,
                    page_size=50,
                )
                files = result.get("data", {}).get("files", [])
                all_files.extend(files)
                page_token = result.get("data", {}).get("next_page_token", "")
                if not page_token or not result.get("data", {}).get("has_more", False):
                    break
            self.finished.emit(all_files)
        except Exception as e:
            self.error.emit(str(e))


class FileBrowserDialog(QDialog):
    """
    云盘文件浏览对话框

    用法::

        dlg = FileBrowserDialog(drive_api, file_type_filter="sheet", parent=self)
        if dlg.exec() == QDialog.Accepted:
            token = dlg.selected_token
            name = dlg.selected_name
    """

    def __init__(self, drive_api, file_type_filter: str = "", parent=None):
        """
        :param drive_api: DriveAPI 实例
        :param file_type_filter: 只显示该类型的文件（如 "sheet" / "bitable"），
                                 空字符串表示显示所有文件
        """
        super().__init__(parent)
        self.drive_api = drive_api
        self.file_type_filter = file_type_filter
        self._worker = None
        self._all_files = []  # 当前文件夹下的所有文件
        self._folder_stack = []  # (folder_token, name) 导航栈

        self.selected_token = ""
        self.selected_name = ""
        self.selected_type = ""

        type_label = {
            "sheet": "表格",
            "bitable": "多维表格",
            "docx": "文档",
        }.get(file_type_filter, "文件")

        self.setWindowTitle(f"📁 从云盘选择{type_label}")
        self.setMinimumSize(520, 480)
        self._setup_ui()
        self._load_files("")

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 导航栏
        nav_layout = QHBoxLayout()
        self.back_btn = QPushButton("⬅ 返回")
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setEnabled(False)
        nav_layout.addWidget(self.back_btn)

        self.path_label = QLabel("📁 我的空间")
        self.path_label.setStyleSheet("font-weight: bold;")
        nav_layout.addWidget(self.path_label, 1)

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setMaximumWidth(30)
        self.refresh_btn.clicked.connect(self._refresh)
        nav_layout.addWidget(self.refresh_btn)
        layout.addLayout(nav_layout)

        # 过滤
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("过滤文件名...")
        self.filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_input)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self._on_item_clicked)
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.file_list)

        # 选中信息
        self.info_label = QLabel("双击文件夹进入，单击文件选中后确定")
        self.info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.info_label)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        self.ok_btn = btn_box.button(QDialogButtonBox.Ok)
        self.ok_btn.setText("✅ 选择")
        self.ok_btn.setEnabled(False)
        layout.addWidget(btn_box)

        # 加载状态
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _load_files(self, folder_token: str):
        """加载文件列表"""
        self.status_label.setText("正在加载...")
        self.file_list.clear()
        self.ok_btn.setEnabled(False)
        self.selected_token = ""
        self.selected_name = ""

        self._worker = _LoadWorker(self.drive_api, folder_token)
        self._worker.finished.connect(self._on_files_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_files_loaded(self, files):
        self._all_files = files
        self._apply_filter(self.filter_input.text())
        self.status_label.setText(f"共 {len(files)} 项")

    def _apply_filter(self, text: str):
        """根据名称过滤并显示文件"""
        self.file_list.clear()
        text_lower = text.lower().strip()

        for f in self._all_files:
            name = f.get("name", "未命名")
            ftype = f.get("type", "file")

            # 名称过滤
            if text_lower and text_lower not in name.lower():
                continue

            # 类型过滤：始终显示文件夹（用于导航），仅过滤文件类型
            if self.file_type_filter and ftype != "folder" and ftype != self.file_type_filter:
                continue

            icon = FILE_TYPE_ICONS.get(ftype, "📄")
            item = QListWidgetItem(f"{icon}  {name}")
            item.setData(Qt.UserRole, f)
            item.setToolTip(f"类型: {ftype}\nToken: {f.get('token', '')}")
            self.file_list.addItem(item)

    def _on_item_clicked(self, item):
        """单击选中"""
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return

        ftype = file_data.get("type", "")
        token = file_data.get("token", "")
        name = file_data.get("name", "")

        if ftype == "folder":
            # 文件夹只能双击进入，单击不选中
            self.info_label.setText(f"📁 {name} — 双击进入文件夹")
            self.ok_btn.setEnabled(False)
            self.selected_token = ""
        else:
            self.selected_token = token
            self.selected_name = name
            self.selected_type = ftype
            self.info_label.setText(f"已选: {name}  |  Token: {token}")
            self.ok_btn.setEnabled(True)

    def _on_item_double_clicked(self, item):
        """双击进入文件夹或直接选择文件"""
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return

        ftype = file_data.get("type", "")
        token = file_data.get("token", "")
        name = file_data.get("name", "")

        if ftype == "folder":
            current_token = self._folder_stack[-1][0] if self._folder_stack else ""
            self._folder_stack.append((token, name))
            self._update_path()
            self.back_btn.setEnabled(True)
            self._load_files(token)
        else:
            # 双击文件直接确认
            self.selected_token = token
            self.selected_name = name
            self.selected_type = ftype
            self.accept()

    def _go_back(self):
        """返回上级"""
        if self._folder_stack:
            self._folder_stack.pop()
            self._update_path()
            self.back_btn.setEnabled(len(self._folder_stack) > 0)
            folder_token = self._folder_stack[-1][0] if self._folder_stack else ""
            self._load_files(folder_token)

    def _refresh(self):
        """刷新当前目录"""
        folder_token = self._folder_stack[-1][0] if self._folder_stack else ""
        self._load_files(folder_token)

    def _update_path(self):
        """更新路径显示"""
        if not self._folder_stack:
            self.path_label.setText("📁 我的空间")
        else:
            path = " > ".join([n for _, n in self._folder_stack])
            self.path_label.setText(f"📁 我的空间 > {path}")

    def _on_ok(self):
        """确认选择"""
        if self.selected_token:
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "请先选择一个文件")

    def _on_error(self, msg):
        self.status_label.setText(f"❌ 错误: {msg}")
        QMessageBox.critical(self, "加载失败", msg)
