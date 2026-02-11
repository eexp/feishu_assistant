"""权限检测 Tab：一键检测飞书应用的所有权限"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from api.auth import FeishuAuth


# 权限检测项定义：(权限名称, 权限 scope, 测试方法, 测试路径, 测试参数)
PERMISSION_CHECKS = [
    {
        "name": "通讯录 - 读取部门",
        "scope": "contact:department.base:readonly",
        "method": "GET",
        "path": "/contact/v3/departments/0/children",
        "params": {"department_id_type": "department_id", "page_size": 1},
        "description": "读取部门列表（联系人 Tab 的部门树功能）",
    },
    {
        "name": "通讯录 - 读取用户",
        "scope": "contact:user.base:readonly",
        "method": "GET",
        "path": "/contact/v3/users/find_by_department",
        "params": {"department_id_type": "department_id", "department_id": "0", "page_size": 1},
        "description": "读取部门下的用户列表",
    },
    {
        "name": "通讯录 - 用户 ID 查询",
        "scope": "contact:user.employee_id:readonly",
        "method": "POST",
        "path": "/contact/v3/users/batch_get_id",
        "params": {"user_id_type": "open_id"},
        "json": {"emails": [], "mobiles": []},
        "description": "通过邮箱/手机号查询用户 ID",
    },
    {
        "name": "消息 - 发送消息",
        "scope": "im:message:send_as_bot",
        "method": "GET",
        "path": "/im/v1/chats",
        "params": {"page_size": 1},
        "description": "机器人发送消息（通过获取群列表验证）",
    },
    {
        "name": "消息 - 读取群信息",
        "scope": "im:chat:readonly",
        "method": "GET",
        "path": "/im/v1/chats",
        "params": {"page_size": 1},
        "description": "获取机器人所在的群列表",
    },
    {
        "name": "云文档 - 读取文件列表",
        "scope": "drive:drive:readonly",
        "method": "GET",
        "path": "/drive/v1/files",
        "params": {"page_size": 1},
        "description": "列出云文档文件（文档 Tab 功能）",
    },
    {
        "name": "云文档 - 读取文档内容",
        "scope": "docx:document:readonly",
        "method": "GET",
        "path": "/docx/v1/documents/placeholder",
        "params": {},
        "description": "读取文档内容（预期 404 即可，非权限错误就算通过）",
        "accept_not_found": True,
    },
    {
        "name": "搜索 - 搜索用户",
        "scope": "search:user",
        "method": "POST",
        "path": "/search/v1/user",
        "params": {"page_size": 1},
        "json": {"query": "test"},
        "description": "搜索用户功能",
    },
]


class PermissionCheckWorker(QThread):
    """逐项检测权限的工作线程"""

    # status: "passed", "failed", "warning"
    progress = Signal(int, str, str, str)  # index, name, status, detail
    finished = Signal(int, int, int)  # passed_count, warning_count, total_count

    def __init__(self, auth: FeishuAuth):
        super().__init__()
        self.auth = auth

    def run(self):
        passed = 0
        warning = 0
        total = len(PERMISSION_CHECKS)

        for i, check in enumerate(PERMISSION_CHECKS):
            name = check["name"]
            try:
                kwargs = {"params": check.get("params", {})}
                if "json" in check:
                    kwargs["json"] = check["json"]

                self.auth.request(check["method"], check["path"], **kwargs)
                self.progress.emit(i, name, "passed", "权限正常")
                passed += 1
            except Exception as e:
                error_msg = str(e)
                # 某些接口预期会返回 404（如文档内容用了 placeholder ID）
                # 如果错误不是权限错误，则认为权限本身是通过的
                if check.get("accept_not_found") and ("not found" in error_msg.lower() or "1120003" in error_msg):
                    self.progress.emit(i, name, "passed", "权限正常（资源不存在但有权限）")
                    passed += 1
                elif "99991400" in error_msg or "permission" in error_msg.lower() or "99991672" in error_msg:
                    self.progress.emit(i, name, "failed", f"无权限: {error_msg}")
                else:
                    # 其他错误（如参数错误），不一定是权限问题
                    self.progress.emit(i, name, "warning", f"非权限错误（可能正常）: {error_msg}")
                    warning += 1

        self.finished.emit(passed, warning, total)


class PermissionsTab(QWidget):
    """权限检测 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auth = None
        self._worker = None
        self._setup_ui()

    def set_auth(self, auth: FeishuAuth):
        """设置认证实例"""
        self._auth = auth

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 顶部说明和操作 ---
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("一键检测飞书应用的所有 API 权限，确保各功能可正常使用。"))
        top_layout.addStretch()
        self.check_btn = QPushButton("🔍 开始检测")
        self.check_btn.setMinimumWidth(120)
        self.check_btn.setMinimumHeight(36)
        self.check_btn.clicked.connect(self._start_check)
        top_layout.addWidget(self.check_btn)
        layout.addLayout(top_layout)

        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(len(PERMISSION_CHECKS))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # --- 检测结果表格 ---
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["权限名称", "Scope", "状态", "详细信息"])
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.cellDoubleClicked.connect(self._on_detail_clicked)

        # 预填充表格
        self.result_table.setRowCount(len(PERMISSION_CHECKS))
        for i, check in enumerate(PERMISSION_CHECKS):
            self.result_table.setItem(i, 0, QTableWidgetItem(check["name"]))
            self.result_table.setItem(i, 1, QTableWidgetItem(check["scope"]))
            self.result_table.setItem(i, 2, QTableWidgetItem("⏳ 待检测"))
            self.result_table.setItem(i, 3, QTableWidgetItem(check["description"]))

        layout.addWidget(self.result_table)

        # --- 统计和说明 ---
        self.summary_label = QLabel("点击「开始检测」按钮检测所有权限")
        layout.addWidget(self.summary_label)

        help_label = QLabel(
            "💡 如需开通权限，请前往 <a href='https://open.feishu.cn'>飞书开放平台</a> "
            "→ 应用详情 → 权限管理 中添加对应权限，并发布应用版本。"
        )
        help_label.setOpenExternalLinks(True)
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

    def _start_check(self):
        """开始检测"""
        if not self._auth:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.check_btn.setEnabled(False)
        self.check_btn.setText("🔄 检测中...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.summary_label.setText("正在检测...")

        # 重置表格状态
        for i in range(self.result_table.rowCount()):
            self.result_table.setItem(i, 2, QTableWidgetItem("⏳ 检测中..."))
            self.result_table.setItem(i, 3, QTableWidgetItem(""))
            for col in range(4):
                item = self.result_table.item(i, col)
                if item:
                    item.setBackground(QColor(255, 255, 255))

        self._worker = PermissionCheckWorker(self._auth)
        self._worker.progress.connect(self._on_check_progress)
        self._worker.finished.connect(self._on_check_finished)
        self._worker.start()

    def _on_check_progress(self, index, name, status, detail):
        """单项检测完成"""
        self.progress_bar.setValue(index + 1)

        if status == "passed":
            status_text = "✅ 通过"
            bg_color = QColor(220, 255, 220)  # 绿色
        elif status == "failed":
            status_text = "❌ 未通过"
            bg_color = QColor(255, 220, 220)  # 红色
        else:  # warning
            status_text = "⚠️ 异常"
            bg_color = QColor(255, 245, 200)  # 黄色

        self.result_table.setItem(index, 2, QTableWidgetItem(status_text))

        # 详细信息：对于有错误的项，显示"点击查看"链接样式
        detail_item = QTableWidgetItem(detail)
        if status in ("failed", "warning"):
            detail_item.setForeground(QColor(0, 102, 204))  # 蓝色文字，表示可点击
            detail_item.setToolTip("双击查看详细信息")
        self.result_table.setItem(index, 3, detail_item)

        for col in range(4):
            item = self.result_table.item(index, col)
            if item:
                item.setBackground(bg_color)

        # 存储完整的详细信息到 item 的 data 中，用于弹窗展示
        detail_item.setData(Qt.UserRole, detail)

    def _on_detail_clicked(self, row, col):
        """双击详细信息列时弹出完整报错"""
        if col != 3:
            return
        item = self.result_table.item(row, 3)
        if not item:
            return
        detail = item.data(Qt.UserRole)
        if not detail:
            return
        # 只有失败或异常的行才弹出详情
        status_item = self.result_table.item(row, 2)
        if status_item and status_item.text() in ("✅ 通过",):
            return

        name_item = self.result_table.item(row, 0)
        name = name_item.text() if name_item else "未知"
        msg = QMessageBox(self)
        msg.setWindowTitle(f"详细信息 - {name}")
        msg.setIcon(QMessageBox.Information)
        msg.setText(detail)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg.exec()

    def _on_check_finished(self, passed, warning, total):
        """所有检测完成"""
        self.check_btn.setEnabled(True)
        self.check_btn.setText("🔍 重新检测")
        self.progress_bar.setVisible(False)

        failed = total - passed - warning
        parts = [f"{passed} 通过"]
        if warning > 0:
            parts.append(f"{warning} 异常")
        if failed > 0:
            parts.append(f"{failed} 未通过")

        if failed == 0 and warning == 0:
            self.summary_label.setText(f"🎉 全部通过！{passed}/{total} 项权限检测正常。")
        else:
            summary = f"检测完成：{', '.join(parts)}（共 {total} 项）。"
            if failed > 0:
                summary += " 请在飞书开放平台开通对应权限。"
            if warning > 0:
                summary += " 异常项可能是非权限原因导致，请关注。"
            self.summary_label.setText(f"⚠️ {summary}")
