"""多维表格 Tab：多维表格管理 + 数据表列表 + 记录 CRUD"""

import json
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


class RecordDialog(QDialog):
    """记录编辑对话框"""

    def __init__(self, fields: list[dict], record: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑记录" if record else "新建记录")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._inputs = {}
        for field in fields:
            name = field.get("field_name", "")
            field_id = field.get("field_id", "")
            input_widget = QLineEdit()
            if record:
                val = record.get("fields", {}).get(name, "")
                if isinstance(val, (dict, list)):
                    input_widget.setText(json.dumps(val, ensure_ascii=False))
                else:
                    input_widget.setText(str(val) if val is not None else "")
            form.addRow(f"{name}:", input_widget)
            self._inputs[name] = input_widget

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_fields(self) -> dict:
        result = {}
        for name, widget in self._inputs.items():
            val = widget.text().strip()
            if val:
                # 尝试 JSON 解析
                try:
                    result[name] = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    result[name] = val
        return result


class BitableTab(QWidget):
    """多维表格管理 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bitable_api = None
        self._worker = None
        self._current_app_token = ""
        self._current_table_id = ""
        self._current_fields = []
        self._current_records = []
        self._setup_ui()

    def set_api(self, bitable_api):
        self._bitable_api = bitable_api

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 顶部操作区 ---
        top_group = QGroupBox("📋 多维表格操作")
        top_layout = QVBoxLayout(top_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("App Token:"))
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("输入多维表格 App Token 或粘贴 URL")
        row1.addWidget(self.token_input, 1)

        self.open_btn = QPushButton("📂 打开")
        self.open_btn.clicked.connect(self._open_bitable)
        row1.addWidget(self.open_btn)

        self.create_btn = QPushButton("➕ 新建")
        self.create_btn.clicked.connect(self._create_bitable)
        row1.addWidget(self.create_btn)
        top_layout.addLayout(row1)

        self.meta_label = QLabel("未打开多维表格")
        self.meta_label.setStyleSheet("color: #666; font-size: 12px;")
        top_layout.addWidget(self.meta_label)

        layout.addWidget(top_group)

        # --- 主体区 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：数据表列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        table_header = QHBoxLayout()
        table_header.addWidget(QLabel("数据表"))
        self.add_table_btn = QPushButton("➕")
        self.add_table_btn.setMaximumWidth(30)
        self.add_table_btn.clicked.connect(self._create_table)
        self.add_table_btn.setEnabled(False)
        table_header.addWidget(self.add_table_btn)
        left_layout.addLayout(table_header)

        self.table_list = QListWidget()
        self.table_list.itemClicked.connect(self._on_table_selected)
        left_layout.addWidget(self.table_list)

        # 字段列表
        left_layout.addWidget(QLabel("字段"))
        self.field_list = QListWidget()
        left_layout.addWidget(self.field_list)

        # 右侧：记录表
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        record_header = QHBoxLayout()
        self.record_count_label = QLabel("记录")
        record_header.addWidget(self.record_count_label)
        record_header.addStretch()

        self.refresh_records_btn = QPushButton("🔄 刷新")
        self.refresh_records_btn.clicked.connect(self._load_records)
        self.refresh_records_btn.setEnabled(False)
        record_header.addWidget(self.refresh_records_btn)

        self.add_record_btn = QPushButton("➕ 新增")
        self.add_record_btn.clicked.connect(self._add_record)
        self.add_record_btn.setEnabled(False)
        record_header.addWidget(self.add_record_btn)

        self.edit_record_btn = QPushButton("✏️ 编辑")
        self.edit_record_btn.clicked.connect(self._edit_record)
        self.edit_record_btn.setEnabled(False)
        record_header.addWidget(self.edit_record_btn)

        self.delete_record_btn = QPushButton("🗑️ 删除")
        self.delete_record_btn.clicked.connect(self._delete_record)
        self.delete_record_btn.setEnabled(False)
        record_header.addWidget(self.delete_record_btn)

        right_layout.addLayout(record_header)

        self.record_table = QTableWidget()
        self.record_table.setAlternatingRowColors(True)
        self.record_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.record_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.record_table.itemSelectionChanged.connect(self._on_record_selection_changed)
        right_layout.addWidget(self.record_table)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self.status_label = QLabel("就绪 - 请输入多维表格 App Token 或新建")
        layout.addWidget(self.status_label)

    def _extract_token(self, text: str) -> str:
        text = text.strip()
        if "/base/" in text:
            return text.split("/base/")[-1].split("?")[0].split("/")[0]
        return text

    def _open_bitable(self):
        if not self._bitable_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return
        token = self._extract_token(self.token_input.text())
        if not token:
            QMessageBox.warning(self, "提示", "请输入 App Token")
            return
        self._current_app_token = token
        self.status_label.setText("正在加载...")
        self.open_btn.setEnabled(False)
        self._worker = ApiWorker(self._bitable_api.list_tables, token)
        self._worker.finished.connect(self._on_tables_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _create_bitable(self):
        if not self._bitable_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return
        name, ok = QInputDialog.getText(self, "新建多维表格", "名称:")
        if not ok or not name:
            return
        self.status_label.setText("正在创建...")
        self._worker = ApiWorker(self._bitable_api.create_bitable, name)
        self._worker.finished.connect(self._on_bitable_created)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_bitable_created(self, result):
        app = result.get("data", {}).get("app", {})
        token = app.get("app_token", "")
        if token:
            self.token_input.setText(token)
            self._current_app_token = token
            self.meta_label.setText(f"✅ 已创建 | Token: {token}")
            self._open_bitable()

    def _on_tables_loaded(self, result):
        self.open_btn.setEnabled(True)
        self.add_table_btn.setEnabled(True)
        self.table_list.clear()
        tables = result.get("data", {}).get("items", [])
        for tbl in tables:
            name = tbl.get("name", "未命名")
            table_id = tbl.get("table_id", "")
            item = QListWidgetItem(f"📋 {name}")
            item.setData(Qt.UserRole, table_id)
            item.setData(Qt.UserRole + 1, name)
            item.setToolTip(f"Table ID: {table_id}")
            self.table_list.addItem(item)
        self.meta_label.setText(f"Token: {self._current_app_token} | {len(tables)} 个数据表")
        self.status_label.setText(f"已加载 {len(tables)} 个数据表")

    def _on_table_selected(self, item):
        self._current_table_id = item.data(Qt.UserRole)
        self.refresh_records_btn.setEnabled(True)
        self.add_record_btn.setEnabled(True)
        self.status_label.setText(f"正在加载字段和记录...")
        # 先加载字段
        self._worker = ApiWorker(
            self._bitable_api.list_fields, self._current_app_token, self._current_table_id
        )
        self._worker.finished.connect(self._on_fields_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_fields_loaded(self, result):
        self.field_list.clear()
        fields = result.get("data", {}).get("items", [])
        self._current_fields = fields

        type_names = {
            1: "文本", 2: "数字", 3: "单选", 4: "多选", 5: "日期",
            7: "复选框", 11: "人员", 13: "电话", 15: "链接",
            17: "附件", 18: "关联", 20: "公式", 22: "地理位置",
            1001: "创建时间", 1002: "修改时间", 1003: "创建人", 1004: "修改人",
        }

        for f in fields:
            name = f.get("field_name", "")
            ftype = f.get("type", 0)
            type_name = type_names.get(ftype, f"类型{ftype}")
            self.field_list.addItem(f"{name} ({type_name})")

        # 加载记录
        self._load_records()

    def _create_table(self):
        if not self._current_app_token:
            return
        name, ok = QInputDialog.getText(self, "新建数据表", "数据表名称:")
        if not ok or not name:
            return
        self.status_label.setText("正在创建数据表...")
        self._worker = ApiWorker(
            self._bitable_api.create_table, self._current_app_token, name
        )
        self._worker.finished.connect(lambda _: self._open_bitable())
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _load_records(self):
        if not self._current_app_token or not self._current_table_id:
            return
        self.status_label.setText("正在加载记录...")
        self.refresh_records_btn.setEnabled(False)
        self._worker = ApiWorker(
            self._bitable_api.list_records,
            self._current_app_token, self._current_table_id, 100,
        )
        self._worker.finished.connect(self._on_records_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_records_loaded(self, result):
        self.refresh_records_btn.setEnabled(True)
        records = result.get("data", {}).get("items", [])
        self._current_records = records

        field_names = [f.get("field_name", "") for f in self._current_fields]
        # 加 record_id 列
        headers = ["record_id"] + field_names
        self.record_table.setColumnCount(len(headers))
        self.record_table.setHorizontalHeaderLabels(headers)
        self.record_table.setRowCount(len(records))

        for r, rec in enumerate(records):
            self.record_table.setItem(r, 0, QTableWidgetItem(rec.get("record_id", "")))
            fields = rec.get("fields", {})
            for c, fname in enumerate(field_names):
                val = fields.get(fname, "")
                if isinstance(val, (dict, list)):
                    display = json.dumps(val, ensure_ascii=False)[:100]
                else:
                    display = str(val) if val is not None else ""
                self.record_table.setItem(r, c + 1, QTableWidgetItem(display))

        self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        total = result.get("data", {}).get("total", len(records))
        self.record_count_label.setText(f"记录 ({total} 条)")
        self.status_label.setText(f"已加载 {len(records)} 条记录")

    def _on_record_selection_changed(self):
        has_sel = len(self.record_table.selectedItems()) > 0
        self.edit_record_btn.setEnabled(has_sel)
        self.delete_record_btn.setEnabled(has_sel)

    def _add_record(self):
        if not self._current_fields:
            QMessageBox.warning(self, "提示", "请先加载字段")
            return
        dialog = RecordDialog(self._current_fields, parent=self)
        if dialog.exec() == QDialog.Accepted:
            fields = dialog.get_fields()
            if not fields:
                return
            self.status_label.setText("正在创建记录...")
            self._worker = ApiWorker(
                self._bitable_api.create_record,
                self._current_app_token, self._current_table_id, fields,
            )
            self._worker.finished.connect(lambda _: self._load_records())
            self._worker.error.connect(self._on_api_error)
            self._worker.start()

    def _edit_record(self):
        row = self.record_table.currentRow()
        if row < 0 or row >= len(self._current_records):
            return
        record = self._current_records[row]
        record_id = record.get("record_id", "")

        dialog = RecordDialog(self._current_fields, record, parent=self)
        if dialog.exec() == QDialog.Accepted:
            fields = dialog.get_fields()
            if not fields:
                return
            self.status_label.setText("正在更新记录...")
            self._worker = ApiWorker(
                self._bitable_api.update_record,
                self._current_app_token, self._current_table_id, record_id, fields,
            )
            self._worker.finished.connect(lambda _: self._load_records())
            self._worker.error.connect(self._on_api_error)
            self._worker.start()

    def _delete_record(self):
        row = self.record_table.currentRow()
        if row < 0 or row >= len(self._current_records):
            return
        record = self._current_records[row]
        record_id = record.get("record_id", "")

        reply = QMessageBox.question(
            self, "确认删除", f"确定删除记录 {record_id}？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.status_label.setText("正在删除记录...")
        self._worker = ApiWorker(
            self._bitable_api.delete_record,
            self._current_app_token, self._current_table_id, record_id,
        )
        self._worker.finished.connect(lambda _: self._load_records())
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_api_error(self, error_msg):
        self.open_btn.setEnabled(True)
        self.refresh_records_btn.setEnabled(True)
        self.status_label.setText(f"❌ 错误: {error_msg}")
        QMessageBox.critical(self, "API 错误", error_msg)
