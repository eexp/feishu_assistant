"""消息 Tab：选择接收人 + 编辑消息 + 发送"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTextEdit,
    QLabel,
    QGroupBox,
    QFormLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
)
from PySide6.QtCore import Qt, QThread, Signal


class ApiWorker(QThread):
    """通用异步 API 调用线程"""

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


class MessagesTab(QWidget):
    """消息发送 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages_api = None
        self._worker = None
        self._setup_ui()

    def set_api(self, messages_api):
        """设置 API 实例"""
        self._messages_api = messages_api

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 接收对象区域 ---
        target_group = QGroupBox("消息接收对象")
        target_layout = QVBoxLayout(target_group)

        # 接收类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("接收类型:"))
        self.receive_type_combo = QComboBox()
        self.receive_type_combo.addItems(["open_id (用户)", "chat_id (群)", "user_id (用户ID)", "email (邮箱)"])
        self.receive_type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.receive_type_combo)
        target_layout.addLayout(type_layout)

        # ID 输入
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("接收者 ID:"))
        self.receive_id_input = QLineEdit()
        self.receive_id_input.setPlaceholderText("输入接收者的 open_id / chat_id / user_id / email")
        id_layout.addWidget(self.receive_id_input)
        target_layout.addLayout(id_layout)

        # 群列表加载
        chat_layout = QHBoxLayout()
        self.load_chats_btn = QPushButton("加载群列表")
        self.load_chats_btn.clicked.connect(self._load_chats)
        chat_layout.addWidget(self.load_chats_btn)
        target_layout.addLayout(chat_layout)

        self.chat_list = QListWidget()
        self.chat_list.setMaximumHeight(150)
        self.chat_list.itemClicked.connect(self._on_chat_selected)
        self.chat_list.setVisible(False)
        target_layout.addWidget(self.chat_list)

        layout.addWidget(target_group)

        # --- 消息编辑区域 ---
        msg_group = QGroupBox("消息内容")
        msg_layout = QVBoxLayout(msg_group)

        # 消息类型
        msg_type_layout = QHBoxLayout()
        msg_type_layout.addWidget(QLabel("消息类型:"))
        self.msg_type_combo = QComboBox()
        self.msg_type_combo.addItems(["文本消息", "富文本消息 (JSON)", "卡片消息 (JSON)"])
        msg_type_layout.addWidget(self.msg_type_combo)
        msg_layout.addLayout(msg_type_layout)

        # 消息内容
        self.msg_content = QTextEdit()
        self.msg_content.setPlaceholderText("输入消息内容...\n\n文本消息直接输入文字即可。\n富文本和卡片消息请输入 JSON 格式。")
        self.msg_content.setMinimumHeight(200)
        msg_layout.addWidget(self.msg_content)

        layout.addWidget(msg_group)

        # --- 发送按钮 ---
        send_layout = QHBoxLayout()
        send_layout.addStretch()
        self.send_btn = QPushButton("📤 发送消息")
        self.send_btn.setMinimumWidth(150)
        self.send_btn.setMinimumHeight(40)
        self.send_btn.clicked.connect(self._on_send)
        send_layout.addWidget(self.send_btn)
        layout.addLayout(send_layout)

        # --- 状态栏 ---
        self.status_label = QLabel("就绪 - 填写接收者和消息内容后发送")
        layout.addWidget(self.status_label)

    def _on_type_changed(self, index):
        """接收类型切换"""
        is_chat = index == 1  # chat_id
        self.chat_list.setVisible(is_chat)
        self.load_chats_btn.setVisible(is_chat)

        type_map = {
            0: "输入接收者的 open_id",
            1: "输入群的 chat_id，或从下方列表选择",
            2: "输入接收者的 user_id",
            3: "输入接收者的邮箱地址",
        }
        self.receive_id_input.setPlaceholderText(type_map.get(index, ""))

    def _load_chats(self):
        """加载群列表"""
        if not self._messages_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.status_label.setText("正在加载群列表...")
        self.load_chats_btn.setEnabled(False)

        self._worker = ApiWorker(self._messages_api.get_all_chats)
        self._worker.finished.connect(self._on_chats_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_chats_loaded(self, chats):
        """群列表加载完成"""
        self.chat_list.clear()
        self.chat_list.setVisible(True)

        for chat in chats:
            name = chat.get("name", "未命名群")
            chat_id = chat.get("chat_id", "")
            description = chat.get("description", "")
            item = QListWidgetItem(f"{name}  [{chat_id[:16]}...]")
            item.setData(Qt.UserRole, chat_id)
            item.setToolTip(f"群名: {name}\nID: {chat_id}\n描述: {description}")
            self.chat_list.addItem(item)

        self.status_label.setText(f"已加载 {len(chats)} 个群")
        self.load_chats_btn.setEnabled(True)

    def _on_chat_selected(self, item):
        """选择群 - 自动切换接收类型为 chat_id"""
        chat_id = item.data(Qt.UserRole)
        self.receive_id_input.setText(chat_id)
        # 自动切换到 chat_id 类型
        self.receive_type_combo.setCurrentIndex(1)

    def _auto_detect_id_type(self, receive_id: str) -> str:
        """根据 ID 前缀自动检测类型"""
        if receive_id.startswith("oc_"):
            return "chat_id"
        elif receive_id.startswith("ou_"):
            return "open_id"
        elif receive_id.startswith("on_"):
            return "union_id"
        elif "@" in receive_id:
            return "email"
        return None  # 无法自动检测

    def _on_send(self):
        """发送消息"""
        if not self._messages_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        receive_id = self.receive_id_input.text().strip()
        if not receive_id:
            QMessageBox.warning(self, "提示", "请输入接收者 ID")
            return

        content = self.msg_content.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "提示", "请输入消息内容")
            return

        # 解析接收类型（优先自动检测，其次用下拉框选择）
        type_index = self.receive_type_combo.currentIndex()
        receive_id_type_map = {0: "open_id", 1: "chat_id", 2: "user_id", 3: "email"}
        receive_id_type = receive_id_type_map.get(type_index, "open_id")

        # 自动检测 ID 类型，覆盖用户选择（避免误选）
        auto_type = self._auto_detect_id_type(receive_id)
        if auto_type:
            receive_id_type = auto_type

        # 解析消息类型
        msg_type_index = self.msg_type_combo.currentIndex()

        self.status_label.setText("正在发送...")
        self.send_btn.setEnabled(False)

        if msg_type_index == 0:
            # 文本消息
            self._worker = ApiWorker(
                self._messages_api.send_text_message, receive_id, content, receive_id_type
            )
        elif msg_type_index == 1:
            # 富文本消息
            import json
            try:
                post_content = json.loads(content)
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "JSON 格式错误", f"富文本内容 JSON 解析失败:\n{e}")
                self.send_btn.setEnabled(True)
                self.status_label.setText("就绪")
                return
            self._worker = ApiWorker(
                self._messages_api.send_rich_text_message, receive_id, post_content, receive_id_type
            )
        elif msg_type_index == 2:
            # 卡片消息
            import json
            try:
                card_content = json.loads(content)
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "JSON 格式错误", f"卡片内容 JSON 解析失败:\n{e}")
                self.send_btn.setEnabled(True)
                self.status_label.setText("就绪")
                return
            self._worker = ApiWorker(
                self._messages_api.send_interactive_message, receive_id, card_content, receive_id_type
            )

        self._worker.finished.connect(self._on_send_result)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_send_result(self, result):
        """发送结果"""
        self.send_btn.setEnabled(True)
        msg_id = result.get("data", {}).get("message_id", "未知")
        self.status_label.setText(f"✅ 发送成功！消息 ID: {msg_id}")
        QMessageBox.information(self, "发送成功", f"消息已发送\n消息 ID: {msg_id}")

    def _on_api_error(self, error_msg):
        """API 调用出错"""
        self.send_btn.setEnabled(True)
        self.load_chats_btn.setEnabled(True)
        self.status_label.setText(f"❌ 错误: {error_msg}")
        QMessageBox.critical(self, "发送失败", error_msg)
