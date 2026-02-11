"""表格 Tab：表格管理 + 工作表列表 + 数据读写"""

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
    QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal

from ui.file_browser_dialog import FileBrowserDialog


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


class SheetsTab(QWidget):
    """表格管理 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sheets_api = None
        self._drive_api = None
        self._worker = None
        self._current_token = ""
        self._current_sheets = []
        self._current_sheet_id = ""
        self._setup_ui()

    def set_api(self, sheets_api):
        self._sheets_api = sheets_api

    def set_drive_api(self, drive_api):
        """设置云盘 API（用于浏览选择表格）"""
        self._drive_api = drive_api
        self.browse_btn.setEnabled(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 顶部操作区 ---
        top_group = QGroupBox("📊 表格操作")
        top_layout = QVBoxLayout(top_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("表格 Token:"))
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("输入 Spreadsheet Token 或粘贴 URL")
        row1.addWidget(self.token_input, 1)

        self.open_btn = QPushButton("📂 打开")
        self.open_btn.clicked.connect(self._open_spreadsheet)
        row1.addWidget(self.open_btn)

        self.browse_btn = QPushButton("📁 浏览云盘")
        self.browse_btn.setToolTip("从云盘中浏览选择表格")
        self.browse_btn.clicked.connect(self._browse_from_drive)
        self.browse_btn.setEnabled(False)
        row1.addWidget(self.browse_btn)

        self.create_btn = QPushButton("➕ 新建表格")
        self.create_btn.clicked.connect(self._create_spreadsheet)
        row1.addWidget(self.create_btn)
        top_layout.addLayout(row1)

        self.meta_label = QLabel("未打开表格")
        self.meta_label.setStyleSheet("color: #666; font-size: 12px;")
        top_layout.addWidget(self.meta_label)

        layout.addWidget(top_group)

        # --- 主体区 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：工作表列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        sheet_header = QHBoxLayout()
        sheet_header.addWidget(QLabel("工作表"))
        self.add_sheet_btn = QPushButton("➕ 新增")
        self.add_sheet_btn.setMaximumWidth(60)
        self.add_sheet_btn.clicked.connect(self._add_sheet)
        self.add_sheet_btn.setEnabled(False)
        sheet_header.addWidget(self.add_sheet_btn)
        left_layout.addLayout(sheet_header)

        self.sheet_list = QListWidget()
        self.sheet_list.itemClicked.connect(self._on_sheet_selected)
        left_layout.addWidget(self.sheet_list)

        # 右侧：数据显示
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        data_header = QHBoxLayout()
        data_header.addWidget(QLabel("范围:"))
        self.range_input = QLineEdit()
        self.range_input.setPlaceholderText("如 A1:D10（空则读取全部）")
        self.range_input.setMaximumWidth(200)
        data_header.addWidget(self.range_input)

        self.read_btn = QPushButton("📖 读取")
        self.read_btn.clicked.connect(self._read_data)
        self.read_btn.setEnabled(False)
        data_header.addWidget(self.read_btn)

        self.write_btn = QPushButton("✏️ 写入")
        self.write_btn.clicked.connect(self._write_data)
        self.write_btn.setEnabled(False)
        data_header.addWidget(self.write_btn)

        self.append_btn = QPushButton("📎 追加")
        self.append_btn.clicked.connect(self._append_data)
        self.append_btn.setEnabled(False)
        data_header.addWidget(self.append_btn)

        right_layout.addLayout(data_header)

        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.data_table)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        layout.addWidget(splitter)

        self.status_label = QLabel("就绪 - 请输入表格 Token 或新建表格")
        layout.addWidget(self.status_label)

    def _extract_token(self, text: str) -> str:
        text = text.strip()
        if "/sheets/" in text:
            return text.split("/sheets/")[-1].split("?")[0].split("/")[0]
        return text

    def _open_spreadsheet(self):
        if not self._sheets_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return
        token = self._extract_token(self.token_input.text())
        if not token:
            QMessageBox.warning(self, "提示", "请输入表格 Token")
            return
        self._current_token = token
        self.status_label.setText("正在加载表格...")
        self.open_btn.setEnabled(False)
        self._worker = ApiWorker(self._sheets_api.list_sheets, token)
        self._worker.finished.connect(self._on_sheets_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _create_spreadsheet(self):
        if not self._sheets_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return
        title, ok = QInputDialog.getText(self, "新建表格", "表格标题:")
        if not ok or not title:
            return
        self.status_label.setText("正在创建表格...")
        self._worker = ApiWorker(self._sheets_api.create_spreadsheet, title)
        self._worker.finished.connect(self._on_spreadsheet_created)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_spreadsheet_created(self, result):
        data = result.get("data", {}).get("spreadsheet", {})
        token = data.get("spreadsheet_token", "")
        title = data.get("title", "")
        if token:
            self.token_input.setText(token)
            self._current_token = token
            self.meta_label.setText(f"✅ 已创建: {title} | Token: {token}")
            self.status_label.setText(f"表格 [{title}] 创建成功")
            self._open_spreadsheet()
        else:
            self.status_label.setText("创建失败")

    def _on_sheets_loaded(self, result):
        self.open_btn.setEnabled(True)
        self.add_sheet_btn.setEnabled(True)
        self.sheet_list.clear()
        sheets = result.get("data", {}).get("sheets", [])
        self._current_sheets = sheets
        for sheet in sheets:
            title = sheet.get("title", "未命名")
            sheet_id = sheet.get("sheet_id", "")
            row_count = sheet.get("grid_properties", {}).get("row_count", 0)
            col_count = sheet.get("grid_properties", {}).get("column_count", 0)
            item = QListWidgetItem(f"📋 {title} ({row_count}×{col_count})")
            item.setData(Qt.UserRole, sheet_id)
            item.setData(Qt.UserRole + 1, title)
            item.setToolTip(f"Sheet ID: {sheet_id}\n行数: {row_count}\n列数: {col_count}")
            self.sheet_list.addItem(item)
        self.meta_label.setText(f"Token: {self._current_token} | {len(sheets)} 个工作表")
        self.status_label.setText(f"已加载 {len(sheets)} 个工作表")

    def _on_sheet_selected(self, item):
        self._current_sheet_id = item.data(Qt.UserRole)
        sheet_title = item.data(Qt.UserRole + 1)
        self.read_btn.setEnabled(True)
        self.write_btn.setEnabled(True)
        self.append_btn.setEnabled(True)
        self.status_label.setText(f"已选择工作表: {sheet_title} ({self._current_sheet_id})")

    def _add_sheet(self):
        if not self._current_token:
            return
        title, ok = QInputDialog.getText(self, "新增工作表", "工作表标题:")
        if not ok or not title:
            return
        self.status_label.setText("正在创建工作表...")
        self._worker = ApiWorker(self._sheets_api.add_sheet, self._current_token, title)
        self._worker.finished.connect(lambda _: self._open_spreadsheet())
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _read_data(self):
        if not self._current_token or not self._current_sheet_id:
            return
        range_str = self.range_input.text().strip()
        full_range = f"{self._current_sheet_id}!{range_str}" if range_str else self._current_sheet_id
        self.status_label.setText("正在读取数据...")
        self.read_btn.setEnabled(False)
        self._worker = ApiWorker(self._sheets_api.read_data, self._current_token, full_range)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_data_loaded(self, result):
        self.read_btn.setEnabled(True)
        values = result.get("data", {}).get("valueRange", {}).get("values", [])
        if not values:
            self.data_table.setRowCount(0)
            self.data_table.setColumnCount(0)
            self.status_label.setText("无数据")
            return
        max_cols = max(len(row) for row in values)
        self.data_table.setRowCount(len(values))
        self.data_table.setColumnCount(max_cols)
        for r, row in enumerate(values):
            for c, cell in enumerate(row):
                self.data_table.setItem(r, c, QTableWidgetItem(str(cell) if cell is not None else ""))
        self.status_label.setText(f"已加载 {len(values)} 行 × {max_cols} 列")

    def _write_data(self):
        if not self._current_token or not self._current_sheet_id:
            return
        row_count = self.data_table.rowCount()
        col_count = self.data_table.columnCount()
        if row_count == 0 or col_count == 0:
            QMessageBox.warning(self, "提示", "表格无数据可写入")
            return
        values = []
        for r in range(row_count):
            row = []
            for c in range(col_count):
                item = self.data_table.item(r, c)
                row.append(item.text() if item else "")
            values.append(row)
        range_str = self.range_input.text().strip()
        if range_str:
            full_range = f"{self._current_sheet_id}!{range_str}"
        else:
            end_col = chr(ord("A") + min(col_count - 1, 25))
            full_range = f"{self._current_sheet_id}!A1:{end_col}{row_count}"
        self.status_label.setText("正在写入数据...")
        self.write_btn.setEnabled(False)
        self._worker = ApiWorker(self._sheets_api.write_data, self._current_token, full_range, values)
        self._worker.finished.connect(self._on_write_success)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_write_success(self, _result):
        self.write_btn.setEnabled(True)
        self.status_label.setText("✅ 数据写入成功")

    def _append_data(self):
        if not self._current_token or not self._current_sheet_id:
            return
        row_count = self.data_table.rowCount()
        col_count = self.data_table.columnCount()
        if row_count == 0 or col_count == 0:
            QMessageBox.warning(self, "提示", "表格无数据可追加")
            return
        values = []
        for r in range(row_count):
            row = []
            for c in range(col_count):
                item = self.data_table.item(r, c)
                row.append(item.text() if item else "")
            values.append(row)
        end_col = chr(ord("A") + min(col_count - 1, 25))
        full_range = f"{self._current_sheet_id}!A:{end_col}"
        self.status_label.setText("正在追加数据...")
        self.append_btn.setEnabled(False)
        self._worker = ApiWorker(self._sheets_api.append_data, self._current_token, full_range, values)
        self._worker.finished.connect(self._on_append_success)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_append_success(self, _result):
        self.append_btn.setEnabled(True)
        self.status_label.setText("✅ 数据追加成功")

    def _browse_from_drive(self):
        """从云盘浏览选择表格"""
        if not self._drive_api:
            QMessageBox.warning(self, "提示", "云盘 API 未初始化")
            return
        dlg = FileBrowserDialog(self._drive_api, file_type_filter="sheet", parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_token:
            self.token_input.setText(dlg.selected_token)
            self.status_label.setText(f"已选择: {dlg.selected_name}")
            self._open_spreadsheet()

    def _on_api_error(self, error_msg):
        self.open_btn.setEnabled(True)
        self.read_btn.setEnabled(True)
        self.write_btn.setEnabled(True)
        self.append_btn.setEnabled(True)
        self.status_label.setText(f"❌ 错误: {error_msg}")
        QMessageBox.critical(self, "API 错误", error_msg)
