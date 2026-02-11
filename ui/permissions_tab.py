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


# 权限检测项定义：按模块分类，覆盖系统所有 API 请求
PERMISSION_CHECKS = [
    # ━━━ 通讯录模块（联系人 Tab）━━━
    {
        "name": "通讯录 - 读取部门",
        "scope": "contact:department.base:readonly",
        "method": "GET",
        "path": "/contact/v3/departments/0/children",
        "params": {"department_id_type": "department_id", "page_size": 1},
        "description": "读取部门列表（联系人 Tab 的部门树功能）",
        "module": "contacts",
    },
    {
        "name": "通讯录 - 读取部门用户",
        "scope": "contact:user.base:readonly",
        "method": "GET",
        "path": "/contact/v3/users/find_by_department",
        "params": {"department_id_type": "department_id", "department_id": "0", "page_size": 1},
        "description": "读取部门下的用户列表",
        "module": "contacts",
    },
    {
        "name": "通讯录 - 查询用户信息",
        "scope": "contact:user.base:readonly",
        "method": "GET",
        "path": "/contact/v3/users/placeholder_user_id",
        "params": {"user_id_type": "open_id"},
        "description": "获取单个用户详细信息（预期 404 即可）",
        "accept_not_found": True,
        "module": "contacts",
    },
    {
        "name": "通讯录 - 用户 ID 查询",
        "scope": "contact:user.employee_id:readonly",
        "method": "POST",
        "path": "/contact/v3/users/batch_get_id",
        "params": {"user_id_type": "open_id"},
        "json": {"emails": [], "mobiles": []},
        "description": "通过邮箱/手机号查询用户 ID",
        "module": "contacts",
    },
    {
        "name": "通讯录 - 搜索用户",
        "scope": "search:user",
        "method": "POST",
        "path": "/search/v1/user",
        "params": {"page_size": 1},
        "json": {"query": "test"},
        "description": "搜索用户功能",
        "module": "contacts",
    },
    # ━━━ 消息模块（消息 Tab）━━━
    {
        "name": "消息 - 获取群列表",
        "scope": "im:chat:readonly",
        "method": "GET",
        "path": "/im/v1/chats",
        "params": {"page_size": 1},
        "description": "获取机器人所在的群列表",
        "module": "messages",
    },
    {
        "name": "消息 - 获取群信息",
        "scope": "im:chat",
        "method": "GET",
        "path": "/im/v1/chats/oc_000000000000000000000",
        "params": {},
        "description": "获取指定群聊详细信息（预期 404 即可）",
        "accept_not_found": True,
        "module": "messages",
    },
    {
        "name": "消息 - 获取群成员",
        "scope": "im:chat.member:readonly",
        "method": "GET",
        "path": "/im/v1/chats/oc_000000000000000000000/members",
        "params": {"page_size": 1},
        "description": "获取群聊成员列表（预期 404 即可）",
        "accept_not_found": True,
        "module": "messages",
    },
    {
        "name": "消息 - 获取群历史消息",
        "scope": "im:message.group_msg",
        "method": "GET",
        "path": "/im/v1/messages",
        "params": {
            "container_id_type": "chat",
            "container_id": "__DYNAMIC_CHAT_ID__",
            "page_size": 1,
        },
        "description": "获取群组历史消息（读取历史消息功能的核心权限）",
        "accept_not_found": True,
        "needs_real_chat_id": True,
        "chat_type": "group",
        "module": "messages",
    },
    {
        "name": "消息 - 获取单聊历史消息",
        "scope": "im:message.p2p_msg",
        "method": "GET",
        "path": "/im/v1/messages",
        "params": {
            "container_id_type": "chat",
            "container_id": "__DYNAMIC_CHAT_ID__",
            "page_size": 1,
        },
        "description": "获取单聊历史消息（p2p 场景需要此权限）",
        "accept_not_found": True,
        "needs_real_chat_id": True,
        "chat_type": "p2p",
        "module": "messages",
    },
    {
        "name": "消息 - 发送消息",
        "scope": "im:message:send_as_bot",
        "method": "GET",
        "path": "/im/v1/chats",
        "params": {"page_size": 1},
        "description": "机器人发送消息（通过获取群列表间接验证）",
        "module": "messages",
    },
    # ━━━ 云文档模块（文档 Tab）━━━
    {
        "name": "云文档 - 读取文件列表",
        "scope": "drive:drive:readonly",
        "method": "GET",
        "path": "/drive/v1/files",
        "params": {"page_size": 1},
        "description": "列出云文档文件列表",
        "module": "documents",
    },
    {
        "name": "云文档 - 读取文档内容",
        "scope": "docx:document:readonly",
        "method": "GET",
        "path": "/docx/v1/documents/placeholder_doc_id/blocks",
        "params": {"page_size": 1},
        "description": "读取文档 Block 内容（预期 404 即可）",
        "accept_not_found": True,
        "module": "documents",
    },
    {
        "name": "云文档 - 搜索文档",
        "scope": "docs:doc",
        "method": "POST",
        "path": "/suite/docs-api/search/object",
        "json": {"search_key": "test", "count": 1, "offset": 0},
        "params": {},
        "description": "搜索云文档",
        "module": "documents",
    },
    {
        "name": "云文档 - 获取文件元数据",
        "scope": "drive:drive:readonly",
        "method": "POST",
        "path": "/drive/v1/metas/batch_query",
        "json": {"request_docs": [{"doc_token": "placeholder", "doc_type": "docx"}]},
        "params": {},
        "description": "批量获取文件元数据",
        "accept_not_found": True,
        "module": "documents",
    },
    {
        "name": "云文档 - 创建文档",
        "scope": "docx:document",
        "method": "POST",
        "path": "/docx/v1/documents",
        "json": {"title": "__perm_check_test__"},
        "params": {},
        "description": "创建新文档（文档 Tab 的创建功能）",
        "module": "documents",
    },
    # ━━━ 表格模块（表格 Tab）━━━
    {
        "name": "表格 - 创建表格",
        "scope": "sheets:spreadsheet",
        "method": "POST",
        "path": "/sheets/v3/spreadsheets",
        "json": {"title": "__perm_check_test__"},
        "params": {},
        "description": "创建电子表格",
        "module": "sheets",
    },
    {
        "name": "表格 - 读取工作表列表",
        "scope": "sheets:spreadsheet:readonly",
        "method": "GET",
        "path": "/sheets/v3/spreadsheets/placeholder_token/sheets/query",
        "params": {},
        "description": "获取表格中的工作表列表（预期 404 即可）",
        "accept_not_found": True,
        "module": "sheets",
    },
    {
        "name": "表格 - 读取数据",
        "scope": "sheets:spreadsheet:readonly",
        "method": "GET",
        "path": "/sheets/v2/spreadsheets/placeholder_token/values/Sheet1!A1:A1",
        "params": {"valueRenderOption": "ToString"},
        "description": "读取表格单元格数据（预期 404 即可）",
        "accept_not_found": True,
        "module": "sheets",
    },
    # ━━━ 多维表格模块（多维表格 Tab）━━━
    {
        "name": "多维表格 - 创建多维表格",
        "scope": "bitable:app",
        "method": "POST",
        "path": "/bitable/v1/apps",
        "json": {"name": "__perm_check_test__"},
        "params": {},
        "description": "创建多维表格",
        "module": "bitable",
    },
    {
        "name": "多维表格 - 获取数据表列表",
        "scope": "bitable:app:readonly",
        "method": "GET",
        "path": "/bitable/v1/apps/placeholder_token/tables",
        "params": {"page_size": 1},
        "description": "获取多维表格中的数据表列表（预期 404 即可）",
        "accept_not_found": True,
        "module": "bitable",
    },
    {
        "name": "多维表格 - 读取记录",
        "scope": "bitable:app:readonly",
        "method": "GET",
        "path": "/bitable/v1/apps/placeholder_token/tables/placeholder_table/records",
        "params": {"page_size": 1},
        "description": "获取多维表格记录（预期 404 即可）",
        "accept_not_found": True,
        "module": "bitable",
    },
    # ━━━ 云盘模块（云盘 Tab）━━━
    {
        "name": "云盘 - 根目录元信息",
        "scope": "drive:drive:readonly",
        "method": "GET",
        "path": "/drive/explorer/v2/root_folder/meta",
        "params": {},
        "description": "获取应用根文件夹元信息",
        "module": "drive",
    },
    {
        "name": "云盘 - 创建文件夹",
        "scope": "drive:drive",
        "method": "POST",
        "path": "/drive/v1/files/create_folder",
        "json": {"name": "__perm_check__", "folder_token": "placeholder"},
        "params": {},
        "description": "创建文件夹（预期参数错误即可）",
        "accept_not_found": True,
        "module": "drive",
    },
    {
        "name": "云盘 - 权限管理",
        "scope": "drive:permission",
        "method": "GET",
        "path": "/drive/v1/permissions/placeholder_token/members",
        "params": {"type": "docx"},
        "description": "获取文档协作者列表（预期 404 即可）",
        "accept_not_found": True,
        "module": "drive",
    },
    # ━━━ 日历模块（日历 Tab）━━━
    {
        "name": "日历 - 获取日历列表",
        "scope": "calendar:calendar:readonly",
        "method": "GET",
        "path": "/calendar/v4/calendars",
        "params": {},
        "description": "获取日历列表",
        "module": "calendar",
    },
    {
        "name": "日历 - 创建日程",
        "scope": "calendar:calendar",
        "method": "GET",
        "path": "/calendar/v4/calendars",
        "params": {},
        "description": "创建日程（通过获取日历列表间接验证）",
        "module": "calendar",
    },
    {
        "name": "日历 - 忙闲查询",
        "scope": "calendar:calendar:free_busy:readonly",
        "method": "POST",
        "path": "/calendar/v4/freebusy/list",
        "json": {
            "time_min": "2024-01-01T00:00:00+08:00",
            "time_max": "2024-01-01T23:59:59+08:00",
            "user_id": "placeholder",
        },
        "params": {"user_id_type": "open_id"},
        "description": "查询用户忙闲状态（预期 404 即可）",
        "accept_not_found": True,
        "module": "calendar",
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

    def _fetch_real_chat_ids(self) -> dict[str, str | None]:
        """
        从群列表 API 动态获取真实的 chat_id，按类型分类。
        返回 {"group": chat_id_or_None, "p2p": chat_id_or_None}
        """
        result = {"group": None, "p2p": None}
        try:
            data = self.auth.request("GET", "/im/v1/chats", params={"page_size": 50})
            items = data.get("data", {}).get("items", [])
            for item in items:
                chat_type = item.get("chat_type", "")  # "group" 或 "p2p"
                chat_id = item.get("chat_id", "")
                if chat_type == "group" and not result["group"] and chat_id:
                    result["group"] = chat_id
                elif chat_type == "p2p" and not result["p2p"] and chat_id:
                    result["p2p"] = chat_id
                if result["group"] and result["p2p"]:
                    break
        except Exception:
            pass
        return result

    def run(self):
        passed = 0
        warning = 0
        total = len(PERMISSION_CHECKS)

        # 预先获取真实的 chat_id，用于历史消息权限检测
        real_chat_ids = self._fetch_real_chat_ids()

        for i, check in enumerate(PERMISSION_CHECKS):
            name = check["name"]

            # 需要真实 chat_id 的检测项：动态替换占位符
            if check.get("needs_real_chat_id"):
                chat_type = check.get("chat_type", "group")
                real_id = real_chat_ids.get(chat_type)
                if not real_id:
                    # 没有对应类型的会话，无法检测，标记为 warning
                    type_label = "群聊" if chat_type == "group" else "单聊"
                    self.progress.emit(
                        i, name, "warning",
                        f"跳过检测：机器人未加入任何{type_label}，无法验证此权限。"
                        f"请将机器人添加到至少一个{type_label}后重新检测。"
                    )
                    warning += 1
                    continue

            try:
                # 深拷贝 params，避免修改原始定义
                params = dict(check.get("params", {}))
                kwargs = {"params": params}
                if "json" in check:
                    kwargs["json"] = check["json"]

                # 替换动态 chat_id 占位符
                if check.get("needs_real_chat_id"):
                    chat_type = check.get("chat_type", "group")
                    real_id = real_chat_ids.get(chat_type)
                    if "__DYNAMIC_CHAT_ID__" in params.get("container_id", ""):
                        params["container_id"] = real_id

                self.auth.request(check["method"], check["path"], **kwargs)
                self.progress.emit(i, name, "passed", "权限正常")
                passed += 1
            except Exception as e:
                error_msg = str(e)
                # 权限相关的飞书错误码
                perm_error_codes = [
                    "99991400",   # 无权限
                    "99991672",   # 无权限
                    "99991671",   # scope 不足
                    "99991663",   # 权限不足
                    "230027",     # Lack of necessary permissions
                ]
                # 资源不存在相关错误码/关键词
                not_found_keywords = [
                    "not found", "not_found", "1120003",
                    "230001", "1244002", "1244001",
                    "invalid", "not exist",
                ]

                # 权限错误检测：使用更精确的匹配避免误判
                is_perm_error = any(code in error_msg for code in perm_error_codes) or \
                                "no permission" in error_msg.lower() or \
                                "lack of necessary permissions" in error_msg.lower() or \
                                "forbidden" in error_msg.lower()
                is_not_found = any(kw in error_msg.lower() if kw.isalpha() else kw in error_msg
                                   for kw in not_found_keywords)

                if check.get("accept_not_found") and is_not_found and not is_perm_error:
                    self.progress.emit(i, name, "passed", "权限正常（资源不存在但有权限）")
                    passed += 1
                elif is_perm_error:
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
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["模块", "权限名称", "Scope", "状态", "详细信息"])
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.cellDoubleClicked.connect(self._on_detail_clicked)

        # 模块显示名映射
        module_labels = {
            "contacts": "📒 通讯录",
            "messages": "💬 消息",
            "documents": "📄 云文档",
            "sheets": "📊 表格",
            "bitable": "📋 多维表格",
            "drive": "📁 云盘",
            "calendar": "📅 日历",
        }

        # 预填充表格
        self.result_table.setRowCount(len(PERMISSION_CHECKS))
        for i, check in enumerate(PERMISSION_CHECKS):
            module_name = module_labels.get(check.get("module", ""), check.get("module", ""))
            self.result_table.setItem(i, 0, QTableWidgetItem(module_name))
            self.result_table.setItem(i, 1, QTableWidgetItem(check["name"]))
            self.result_table.setItem(i, 2, QTableWidgetItem(check["scope"]))
            self.result_table.setItem(i, 3, QTableWidgetItem("⏳ 待检测"))
            self.result_table.setItem(i, 4, QTableWidgetItem(check["description"]))

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
            self.result_table.setItem(i, 3, QTableWidgetItem("⏳ 检测中..."))
            self.result_table.setItem(i, 4, QTableWidgetItem(""))
            for col in range(5):
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

        self.result_table.setItem(index, 3, QTableWidgetItem(status_text))

        # 详细信息：对于有错误的项，显示"点击查看"链接样式
        detail_item = QTableWidgetItem(detail)
        if status in ("failed", "warning"):
            detail_item.setForeground(QColor(0, 102, 204))  # 蓝色文字，表示可点击
            detail_item.setToolTip("双击查看详细信息")
        self.result_table.setItem(index, 4, detail_item)

        for col in range(5):
            item = self.result_table.item(index, col)
            if item:
                item.setBackground(bg_color)

        # 存储完整的详细信息到 item 的 data 中，用于弹窗展示
        detail_item.setData(Qt.UserRole, detail)

    def _on_detail_clicked(self, row, col):
        """双击详细信息列时弹出完整报错"""
        if col != 4:
            return
        item = self.result_table.item(row, 4)
        if not item:
            return
        detail = item.data(Qt.UserRole)
        if not detail:
            return
        # 只有失败或异常的行才弹出详情
        status_item = self.result_table.item(row, 3)
        if status_item and status_item.text() in ("✅ 通过",):
            return

        name_item = self.result_table.item(row, 1)
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
