"""云盘 Tab：文件夹管理 + 权限管理"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QLabel,
    QGroupBox,
    QHeaderView,
    QMessageBox,
    QInputDialog,
    QComboBox,
    QTextEdit,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QThread, Signal


class ApiWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AddPermissionDialog(QDialog):
    """添加权限对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加权限")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.member_id_input = QLineEdit()
        self.member_id_input.setPlaceholderText("open_id / user_id / email / chat_id")
        form.addRow("成员 ID:", self.member_id_input)

        self.member_type_combo = QComboBox()
        self.member_type_combo.addItems(["openid", "userid", "email", "openchat", "opendepartmentid"])
        form.addRow("成员类型:", self.member_type_combo)

        self.perm_combo = QComboBox()
        self.perm_combo.addItems(["view", "edit", "full_access"])
        form.addRow("权限:", self.perm_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict:
        return {
            "member_id": self.member_id_input.text().strip(),
            "member_type": self.member_type_combo.currentText(),
            "perm": self.perm_combo.currentText(),
        }


# 文件类型图标
FILE_TYPE_ICONS = {
    "doc": "📝", "docx": "📝", "sheet": "📊", "bitable": "📋",
    "mindnote": "🧠", "folder": "📁", "file": "📄", "slides": "📽️",
}


class DriveTab(QWidget):
    """云盘管理 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drive_api = None
        self._worker = None
        self._folder_stack = []
        self._current_files = []
        self._selected_file = None
        self._setup_ui()

    def set_api(self, drive_api):
        self._drive_api = drive_api

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 主体区 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：文件浏览器
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 路径导航
        nav_layout = QHBoxLayout()
        self.back_btn = QPushButton("⬅ 返回")
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setEnabled(False)
        nav_layout.addWidget(self.back_btn)

        self.path_label = QLabel("根目录")
        nav_layout.addWidget(self.path_label, 1)

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.clicked.connect(self._refresh_files)
        nav_layout.addWidget(self.refresh_btn)

        self.new_folder_btn = QPushButton("📁 新建文件夹")
        self.new_folder_btn.clicked.connect(self._create_folder)
        nav_layout.addWidget(self.new_folder_btn)
        left_layout.addLayout(nav_layout)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self._on_file_clicked)
        self.file_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        left_layout.addWidget(self.file_list)

        # 右侧：文件信息 + 权限管理
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 文件信息
        info_group = QGroupBox("📄 文件信息")
        info_layout = QVBoxLayout(info_group)
        self.file_info_label = QTextEdit()
        self.file_info_label.setReadOnly(True)
        self.file_info_label.setMaximumHeight(120)
        self.file_info_label.setPlaceholderText("选择文件查看详情")
        info_layout.addWidget(self.file_info_label)

        btn_row = QHBoxLayout()
        self.delete_btn = QPushButton("🗑️ 删除文件")
        self.delete_btn.clicked.connect(self._delete_file)
        self.delete_btn.setEnabled(False)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()
        info_layout.addLayout(btn_row)
        right_layout.addWidget(info_group)

        # 权限管理
        perm_group = QGroupBox("🔐 权限管理")
        perm_layout = QVBoxLayout(perm_group)

        perm_header = QHBoxLayout()
        self.load_perm_btn = QPushButton("🔄 加载权限")
        self.load_perm_btn.clicked.connect(self._load_permissions)
        self.load_perm_btn.setEnabled(False)
        perm_header.addWidget(self.load_perm_btn)

        self.add_perm_btn = QPushButton("➕ 添加权限")
        self.add_perm_btn.clicked.connect(self._add_permission)
        self.add_perm_btn.setEnabled(False)
        perm_header.addWidget(self.add_perm_btn)

        perm_header.addStretch()
        perm_layout.addLayout(perm_header)

        self.perm_table = QTableWidget()
        self.perm_table.setColumnCount(4)
        self.perm_table.setHorizontalHeaderLabels(["成员类型", "成员 ID", "权限", "操作"])
        self.perm_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.perm_table.setAlternatingRowColors(True)
        self.perm_table.setEditTriggers(QTableWidget.NoEditTriggers)
        perm_layout.addWidget(self.perm_table)

        right_layout.addWidget(perm_group)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.status_label = QLabel("就绪 - 认证后点击刷新加载文件列表")
        layout.addWidget(self.status_label)

    def _get_current_folder_token(self) -> str:
        return self._folder_stack[-1]["token"] if self._folder_stack else ""

    def _refresh_files(self):
        if not self._drive_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return
        folder_token = self._get_current_folder_token()
        self.status_label.setText("正在加载文件列表...")
        self.refresh_btn.setEnabled(False)
        self._worker = ApiWorker(self._drive_api.list_files, folder_token)
        self._worker.finished.connect(self._on_files_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_files_loaded(self, result):
        self.refresh_btn.setEnabled(True)
        self.file_list.clear()
        files = result.get("data", {}).get("files", [])
        self._current_files = files

        for f in files:
            name = f.get("name", "未命名")
            file_type = f.get("type", "file")
            icon = FILE_TYPE_ICONS.get(file_type, "📄")
            item = QListWidgetItem(f"{icon} {name}")
            item.setData(Qt.UserRole, f)
            item.setToolTip(
                f"名称: {name}\n类型: {file_type}\n"
                f"Token: {f.get('token', '')}\n"
                f"创建: {f.get('created_time', 'N/A')}\n"
                f"修改: {f.get('modified_time', 'N/A')}"
            )
            self.file_list.addItem(item)

        self.status_label.setText(f"已加载 {len(files)} 个文件")

    def _on_file_clicked(self, item):
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return
        self._selected_file = file_data
        name = file_data.get("name", "")
        ftype = file_data.get("type", "")
        token = file_data.get("token", "")

        self.file_info_label.setPlainText(
            f"名称: {name}\n"
            f"类型: {ftype}\n"
            f"Token: {token}\n"
            f"URL: {file_data.get('url', 'N/A')}\n"
            f"所有者: {file_data.get('owner_id', 'N/A')}"
        )

        self.delete_btn.setEnabled(True)
        self.load_perm_btn.setEnabled(True)
        self.add_perm_btn.setEnabled(True)

    def _on_file_double_clicked(self, item):
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return
        if file_data.get("type") == "folder":
            self._folder_stack.append({
                "token": file_data.get("token", ""),
                "name": file_data.get("name", ""),
            })
            self._update_path()
            self.back_btn.setEnabled(True)
            self._refresh_files()

    def _go_back(self):
        if self._folder_stack:
            self._folder_stack.pop()
            self._update_path()
            self.back_btn.setEnabled(len(self._folder_stack) > 0)
            self._refresh_files()

    def _update_path(self):
        if not self._folder_stack:
            self.path_label.setText("根目录")
        else:
            path = " > ".join([f["name"] for f in self._folder_stack])
            self.path_label.setText(f"根目录 > {path}")

    def _create_folder(self):
        if not self._drive_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称:")
        if not ok or not name:
            return
        parent = self._get_current_folder_token()
        self.status_label.setText("正在创建文件夹...")
        self._worker = ApiWorker(self._drive_api.create_folder, name, parent if parent else "")
        self._worker.finished.connect(lambda _: self._refresh_files())
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _delete_file(self):
        if not self._selected_file:
            return
        name = self._selected_file.get("name", "")
        token = self._selected_file.get("token", "")
        ftype = self._selected_file.get("type", "file")

        reply = QMessageBox.question(
            self, "确认删除", f"确定删除 [{name}]？此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.status_label.setText("正在删除...")
        self._worker = ApiWorker(self._drive_api.delete_file, token, ftype)
        self._worker.finished.connect(lambda _: self._refresh_files())
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _load_permissions(self):
        if not self._selected_file:
            return
        token = self._selected_file.get("token", "")
        doc_type = self._selected_file.get("type", "file")
        self.status_label.setText("正在加载权限...")
        self._worker = ApiWorker(self._drive_api.get_permission_members, token, doc_type)
        self._worker.finished.connect(self._on_permissions_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_permissions_loaded(self, result):
        members = result.get("data", {}).get("items", [])
        self.perm_table.setRowCount(len(members))
        for r, m in enumerate(members):
            self.perm_table.setItem(r, 0, QTableWidgetItem(m.get("member_type", "")))
            self.perm_table.setItem(r, 1, QTableWidgetItem(m.get("member_id", "")))
            self.perm_table.setItem(r, 2, QTableWidgetItem(m.get("perm", "")))

            remove_btn = QPushButton("移除")
            member_id = m.get("member_id", "")
            member_type = m.get("member_type", "")
            remove_btn.clicked.connect(
                lambda checked, mid=member_id, mt=member_type: self._remove_permission(mid, mt)
            )
            self.perm_table.setCellWidget(r, 3, remove_btn)

        self.status_label.setText(f"已加载 {len(members)} 个协作者")

    def _add_permission(self):
        if not self._selected_file:
            return
        dialog = AddPermissionDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.get_values()
        if not values["member_id"]:
            QMessageBox.warning(self, "提示", "请输入成员 ID")
            return

        token = self._selected_file.get("token", "")
        doc_type = self._selected_file.get("type", "file")

        self.status_label.setText("正在添加权限...")
        self._worker = ApiWorker(
            self._drive_api.add_permission,
            token, doc_type, values["member_id"],
            values["member_type"], values["perm"],
        )
        self._worker.finished.connect(lambda _: self._load_permissions())
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _remove_permission(self, member_id: str, member_type: str):
        if not self._selected_file:
            return
        reply = QMessageBox.question(
            self, "确认", f"确定移除 {member_id} 的权限？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        token = self._selected_file.get("token", "")
        doc_type = self._selected_file.get("type", "file")

        self.status_label.setText("正在移除权限...")
        self._worker = ApiWorker(
            self._drive_api.remove_permission,
            token, doc_type, member_id, member_type,
        )
        self._worker.finished.connect(lambda _: self._load_permissions())
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_api_error(self, error_msg):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"❌ 错误: {error_msg}")
        QMessageBox.critical(self, "API 错误", error_msg)
