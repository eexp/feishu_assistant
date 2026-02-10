"""联系人 Tab：部门树 + 用户列表 + 搜索"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QLabel,
    QHeaderView,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal


class ApiWorker(QThread):
    """通用异步 API 调用线程"""

    finished = Signal(object)  # 成功时发射结果
    error = Signal(str)  # 失败时发射错误信息

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


class ContactsTab(QWidget):
    """联系人管理 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._contacts_api = None
        self._worker = None
        self._setup_ui()

    def set_api(self, contacts_api):
        """设置 API 实例（认证成功后调用）"""
        self._contacts_api = contacts_api

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 顶部搜索区 ---
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索用户（姓名/手机号/邮箱）...")
        self.search_input.returnPressed.connect(self._on_search)
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        # --- 主体区：左侧部门树 + 右侧用户表 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：部门树
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        dept_header = QHBoxLayout()
        dept_header.addWidget(QLabel("部门列表"))
        self.refresh_dept_btn = QPushButton("刷新")
        self.refresh_dept_btn.clicked.connect(self._load_departments)
        dept_header.addWidget(self.refresh_dept_btn)
        left_layout.addLayout(dept_header)

        self.dept_tree = QTreeWidget()
        self.dept_tree.setHeaderLabels(["部门名称", "部门ID"])
        self.dept_tree.setColumnWidth(0, 200)
        self.dept_tree.itemClicked.connect(self._on_department_clicked)
        left_layout.addWidget(self.dept_tree)

        # 右侧：用户表
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.user_count_label = QLabel("用户列表")
        right_layout.addWidget(self.user_count_label)

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(5)
        self.user_table.setHorizontalHeaderLabels(["姓名", "英文名", "手机号", "邮箱", "Open ID"])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.user_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.user_table)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # --- 状态栏 ---
        self.status_label = QLabel("就绪 - 请先认证后刷新部门列表")
        layout.addWidget(self.status_label)

    def _load_departments(self):
        """加载部门列表"""
        if not self._contacts_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.status_label.setText("正在加载部门列表...")
        self.refresh_dept_btn.setEnabled(False)

        self._worker = ApiWorker(self._contacts_api.get_all_departments, "0")
        self._worker.finished.connect(self._on_departments_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_departments_loaded(self, departments):
        """部门数据加载完成"""
        self.dept_tree.clear()

        # 构建部门树
        dept_map = {}
        root_items = []

        for dept in departments:
            item = QTreeWidgetItem()
            item.setText(0, dept.get("name", "未知"))
            item.setText(1, dept.get("department_id", ""))
            item.setData(0, Qt.UserRole, dept)
            dept_map[dept.get("department_id", "")] = item

        # 建立父子关系
        for dept in departments:
            dept_id = dept.get("department_id", "")
            parent_id = dept.get("parent_department_id", "0")
            item = dept_map.get(dept_id)

            if parent_id in dept_map:
                dept_map[parent_id].addChild(item)
            else:
                root_items.append(item)

        self.dept_tree.addTopLevelItems(root_items)
        self.dept_tree.expandAll()

        self.status_label.setText(f"已加载 {len(departments)} 个部门")
        self.refresh_dept_btn.setEnabled(True)

    def _on_department_clicked(self, item, column):
        """点击部门，加载该部门下的用户"""
        dept_id = item.text(1)
        if not dept_id:
            return

        self.status_label.setText(f"正在加载部门 [{item.text(0)}] 的用户...")
        self._worker = ApiWorker(self._contacts_api.get_all_department_users, dept_id)
        self._worker.finished.connect(self._on_users_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_users_loaded(self, users):
        """用户数据加载完成"""
        self.user_table.setRowCount(0)
        self.user_table.setRowCount(len(users))

        for row, user in enumerate(users):
            self.user_table.setItem(row, 0, QTableWidgetItem(user.get("name", "")))
            self.user_table.setItem(row, 1, QTableWidgetItem(user.get("en_name", "")))
            self.user_table.setItem(row, 2, QTableWidgetItem(user.get("mobile", "")))
            self.user_table.setItem(row, 3, QTableWidgetItem(user.get("email", "")))
            self.user_table.setItem(row, 4, QTableWidgetItem(user.get("open_id", "")))

        self.user_count_label.setText(f"用户列表 ({len(users)} 人)")
        self.status_label.setText(f"已加载 {len(users)} 个用户")

    def _on_search(self):
        """搜索用户"""
        query = self.search_input.text().strip()
        if not query:
            return
        if not self._contacts_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.status_label.setText(f"正在搜索 [{query}]...")
        self.search_btn.setEnabled(False)

        # 尝试通过手机号/邮箱批量查询
        if "@" in query:
            self._worker = ApiWorker(self._contacts_api.batch_get_user_by_id, emails=[query])
        elif query.isdigit():
            self._worker = ApiWorker(self._contacts_api.batch_get_user_by_id, mobiles=[query])
        else:
            self._worker = ApiWorker(self._contacts_api.search_user, query)

        self._worker.finished.connect(self._on_search_result)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_search_result(self, result):
        """搜索结果返回"""
        self.search_btn.setEnabled(True)
        data = result.get("data", {})

        # 处理 batch_get_user_by_id 结果
        if "user_list" in data:
            users = data["user_list"]
            self.user_table.setRowCount(0)
            self.user_table.setRowCount(len(users))
            for row, user in enumerate(users):
                self.user_table.setItem(row, 0, QTableWidgetItem(""))
                self.user_table.setItem(row, 1, QTableWidgetItem(""))
                self.user_table.setItem(row, 2, QTableWidgetItem(user.get("mobile", "")))
                self.user_table.setItem(row, 3, QTableWidgetItem(user.get("email", "")))
                self.user_table.setItem(row, 4, QTableWidgetItem(user.get("user_id", "")))
            self.user_count_label.setText(f"搜索结果 ({len(users)} 人)")
            self.status_label.setText(f"找到 {len(users)} 个匹配用户")
        # 处理 search_user 结果
        elif "users" in data:
            users = data["users"]
            self.user_table.setRowCount(0)
            self.user_table.setRowCount(len(users))
            for row, user in enumerate(users):
                self.user_table.setItem(row, 0, QTableWidgetItem(user.get("name", "")))
                self.user_table.setItem(row, 1, QTableWidgetItem(user.get("en_name", "")))
                self.user_table.setItem(row, 2, QTableWidgetItem(""))
                self.user_table.setItem(row, 3, QTableWidgetItem(""))
                self.user_table.setItem(row, 4, QTableWidgetItem(user.get("open_id", "")))
            self.user_count_label.setText(f"搜索结果 ({len(users)} 人)")
            self.status_label.setText(f"找到 {len(users)} 个匹配用户")
        else:
            self.status_label.setText("未找到匹配结果")

    def _on_api_error(self, error_msg):
        """API 调用出错"""
        self.status_label.setText(f"错误: {error_msg}")
        self.refresh_dept_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        QMessageBox.critical(self, "API 错误", error_msg)
