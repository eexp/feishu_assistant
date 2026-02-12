"""消息 Tab：左侧选择消息对象 + 右侧聊天框与发送"""

import json
import time
from datetime import datetime, timezone, timedelta
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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QScrollArea,
    QSizePolicy,
    QFrame,
    QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QUrl
from PySide6.QtGui import QFont, QColor, QTextCursor, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


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


def text_to_post(text: str, title: str = "") -> dict:
    """
    将纯文本转换为飞书富文本 post 格式。
    每行文本作为一个段落，空行保留。
    """
    lines = text.split("\n")
    content = []
    for line in lines:
        if line.strip():
            content.append([{"tag": "text", "text": line}])
        else:
            content.append([{"tag": "text", "text": ""}])

    return {
        "zh_cn": {
            "title": title,
            "content": content,
        }
    }


def _parse_msg_content(msg: dict) -> str:
    """从消息体中提取可读文本"""
    msg_type = msg.get("msg_type", "")
    body = msg.get("body", {})
    content_str = body.get("content", "{}")

    try:
        content = json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        content = {}

    if msg_type == "text":
        return content.get("text", content_str)
    elif msg_type == "post":
        # 富文本：提取所有 text 标签的文本
        parts = []
        zh = content.get("zh_cn", content.get("en_us", {}))
        title = zh.get("title", "")
        if title:
            parts.append(f"[{title}]")
        for paragraph in zh.get("content", []):
            line_parts = []
            for elem in paragraph:
                tag = elem.get("tag", "")
                if tag == "text":
                    line_parts.append(elem.get("text", ""))
                elif tag == "a":
                    line_parts.append(elem.get("text", "") + f"({elem.get('href', '')})")
                elif tag == "at":
                    line_parts.append(f"@{elem.get('user_name', elem.get('user_id', ''))}")
                elif tag == "img":
                    line_parts.append("[图片]")
                elif tag == "media":
                    line_parts.append("[媒体]")
            parts.append("".join(line_parts))
        return "\n".join(parts)
    elif msg_type == "image":
        return "[图片消息]"
    elif msg_type == "file":
        return f"[文件] {content.get('file_name', '')}"
    elif msg_type == "audio":
        return "[语音消息]"
    elif msg_type == "sticker":
        return "[表情]"
    elif msg_type == "interactive":
        # 卡片消息
        header = content.get("header", {})
        title = header.get("title", {}).get("content", "")
        return f"[卡片] {title}" if title else "[卡片消息]"
    elif msg_type == "share_chat":
        return f"[分享群聊] {content.get('chat_name', '')}"
    elif msg_type == "share_user":
        return "[分享名片]"
    elif msg_type == "system":
        return "[系统消息]"
    elif msg_type == "merge_forward":
        return "[合并转发]"
    else:
        return f"[{msg_type}]"


class MessagesTab(QWidget):
    """消息 Tab - 左侧选择对象，右侧聊天与发送"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages_api = None
        self._worker = None
        self._old_workers = []  # 保持旧 worker 引用，防止被 GC 提前销毁
        self._current_chat_id = None
        self._current_chat_name = ""
        self._chat_data_cache = {}  # chat_id -> chat info
        self._p2p_contacts = {}  # owner_id(open_id) -> {chat_id, name} 去重的单聊联系人
        self._avatar_cache = {}  # chat_id -> QIcon
        self._net_manager = QNetworkAccessManager(self)
        self._setup_ui()

    def set_api(self, messages_api):
        """设置 API 实例"""
        self._messages_api = messages_api

    def _start_new_worker(self, worker):
        """
        安全地启动新 worker，妥善处理旧 worker 的生命周期。
        防止 QThread 在回调中被替换时过早销毁导致崩溃。
        """
        if self._worker is not None:
            # 将旧 worker 移入保留列表，防止 GC
            self._old_workers.append(self._worker)
            # 安排旧 worker 延迟销毁
            self._worker.deleteLater()
        self._worker = worker
        # 清理已完成的旧 workers
        self._old_workers = [w for w in self._old_workers if w.isRunning()]
        self._worker.start()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # ===== 左侧面板：消息对象选择 (20%) =====
        left_panel = QWidget()
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(6)

        # 标题
        left_title = QLabel("💬 消息对象")
        left_title.setFont(QFont("", 13, QFont.Bold))
        left_layout.addWidget(left_title)

        # 加载群列表按钮
        self.load_chats_btn = QPushButton("🔄 加载会话列表")
        self.load_chats_btn.clicked.connect(self._load_chats)
        left_layout.addWidget(self.load_chats_btn)

        # 会话类型过滤 + 搜索框（横排）
        filter_row = QHBoxLayout()
        self.chat_type_filter = QComboBox()
        self.chat_type_filter.addItems(["全部", "群聊", "单聊"])
        self.chat_type_filter.setToolTip("按会话类型过滤")
        self.chat_type_filter.currentIndexChanged.connect(self._filter_chat_list)
        filter_row.addWidget(self.chat_type_filter)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索会话...")
        self.search_input.textChanged.connect(self._filter_chat_list)
        filter_row.addWidget(self.search_input, 1)
        left_layout.addLayout(filter_row)

        # 会话列表
        self.chat_list = QListWidget()
        self.chat_list.setIconSize(QSize(32, 32))
        self.chat_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #fafafa;
            }
            QListWidget::item {
                padding: 8px 6px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #1565c0;
            }
            QListWidget::item:hover {
                background: #f0f0f0;
            }
        """)
        self.chat_list.itemClicked.connect(self._on_chat_selected)
        left_layout.addWidget(self.chat_list)

        # 手动输入 ID 区域
        manual_group = QGroupBox("手动指定")
        manual_layout = QVBoxLayout(manual_group)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("类型:"))
        self.receive_type_combo = QComboBox()
        self.receive_type_combo.addItems(["chat_id (群)", "open_id (用户)", "user_id", "email"])
        type_row.addWidget(self.receive_type_combo)
        manual_layout.addLayout(type_row)

        self.manual_id_input = QLineEdit()
        self.manual_id_input.setPlaceholderText("输入 chat_id / open_id / ...")
        manual_layout.addWidget(self.manual_id_input)

        self.manual_open_btn = QPushButton("📨 打开会话")
        self.manual_open_btn.clicked.connect(self._on_manual_open)
        manual_layout.addWidget(self.manual_open_btn)

        left_layout.addWidget(manual_group)

        # 状态标签
        self.left_status = QLabel("请加载会话列表")
        self.left_status.setStyleSheet("color: #888; font-size: 11px;")
        left_layout.addWidget(self.left_status)

        main_layout.addWidget(left_panel, 2)  # stretch factor 2 (≈20%)

        # ===== 右侧面板：聊天区域 (80%) =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(6)

        # 聊天标题栏
        header_layout = QHBoxLayout()
        self.chat_title_label = QLabel("请选择一个会话")
        self.chat_title_label.setFont(QFont("", 14, QFont.Bold))
        header_layout.addWidget(self.chat_title_label)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 刷新消息")
        self.refresh_btn.clicked.connect(self._load_messages)
        self.refresh_btn.setEnabled(False)
        header_layout.addWidget(self.refresh_btn)

        right_layout.addLayout(header_layout)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(line)

        # 聊天记录显示区域（上方大区域）
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                font-family: -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
            }
        """)
        self.chat_display.setPlaceholderText(
            "选择左侧的会话对象后，历史消息将显示在这里...\n\n"
            "• 点击左侧群聊/会话加载历史消息\n"
            "• 也可以手动输入 ID 打开会话"
        )
        right_layout.addWidget(self.chat_display, 7)  # stretch factor 7

        # ===== 发送区域（下方小区域） =====
        send_group = QGroupBox("发送消息")
        send_layout = QVBoxLayout(send_group)

        # 消息类型选择（单行）
        msg_type_row = QHBoxLayout()
        msg_type_row.addWidget(QLabel("类型:"))
        self.msg_type_combo = QComboBox()
        self.msg_type_combo.addItems(["文本消息", "富文本消息", "卡片消息 (JSON)"])
        self.msg_type_combo.currentIndexChanged.connect(self._on_msg_type_changed)
        msg_type_row.addWidget(self.msg_type_combo)

        # 富文本标题（仅富文本时显示）
        self.title_label = QLabel("标题:")
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("富文本标题（可选）")
        self.title_label.setVisible(False)
        self.title_input.setVisible(False)
        msg_type_row.addWidget(self.title_label)
        msg_type_row.addWidget(self.title_input)

        msg_type_row.addStretch()
        send_layout.addLayout(msg_type_row)

        # 输入区域 + 发送按钮（横排）
        input_row = QHBoxLayout()
        self.msg_input = QTextEdit()
        self.msg_input.setMaximumHeight(80)
        self.msg_input.setMinimumHeight(50)
        self.msg_input.setPlaceholderText("输入消息... (Ctrl+Enter 发送)")
        self.msg_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        input_row.addWidget(self.msg_input, 1)

        self.send_btn = QPushButton("📤 发送")
        self.send_btn.setMinimumWidth(80)
        self.send_btn.setMinimumHeight(50)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #1677ff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #4096ff;
            }
            QPushButton:pressed {
                background: #0958d9;
            }
            QPushButton:disabled {
                background: #bbb;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        self.send_btn.setEnabled(False)
        input_row.addWidget(self.send_btn)

        send_layout.addLayout(input_row)

        right_layout.addWidget(send_group, 2)  # stretch factor 2

        # 状态栏
        self.status_label = QLabel("就绪 - 选择左侧的会话开始聊天")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        right_layout.addWidget(self.status_label)

        main_layout.addWidget(right_panel, 8)  # stretch factor 8 (≈80%)

        # Ctrl+Enter 快捷发送
        self.msg_input.installEventFilter(self)

    def eventFilter(self, obj, event):
        """拦截 Ctrl+Enter 快捷发送"""
        from PySide6.QtCore import QEvent
        if obj == self.msg_input and event.type() == QEvent.KeyPress:
            from PySide6.QtCore import Qt as QtKey
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    # ─── 左侧面板：会话列表 ─────────────────────

    def _load_chats(self):
        """加载机器人所在的群列表"""
        if not self._messages_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.left_status.setText("正在加载会话列表...")
        self.load_chats_btn.setEnabled(False)

        worker = ApiWorker(self._messages_api.get_all_chats)
        worker.finished.connect(self._on_chats_loaded)
        worker.error.connect(self._on_api_error)
        self._start_new_worker(worker)

    def _on_chats_loaded(self, chats):
        """会话列表加载完成"""
        self.chat_list.clear()
        self._chat_data_cache.clear()
        self._p2p_contacts.clear()

        group_count = 0
        all_owner_ids = {}  # owner_id -> 第一个出现的 chat 信息（用于去重）

        # ── 第一轮：显示所有会话，同时收集所有 owner_id ──
        for chat in chats:
            name = chat.get("name", "未命名会话")
            chat_id = chat.get("chat_id", "")
            chat_mode = chat.get("chat_mode", "") or chat.get("chat_type", "")
            description = chat.get("description", "")
            owner_id = chat.get("owner_id", "")
            member_count = chat.get("user_count", "") or chat.get("member_count", "")
            avatar_url = chat.get("avatar", "")

            # 收集所有会话的 owner_id（群聊 + 单聊）
            if owner_id and owner_id not in all_owner_ids:
                all_owner_ids[owner_id] = {
                    "owner_id": owner_id,
                    "first_chat_name": name,
                    "first_chat_id": chat_id,
                }

            # 显示会话条目
            if not chat_mode:
                chat_mode = "group"
            group_count += 1
            display_text = f"👥 {name}"
            if member_count:
                display_text += f" ({member_count}人)"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, chat_id)
            item.setData(Qt.UserRole + 1, name)
            item.setData(Qt.UserRole + 2, "group")  # 会话类型
            item.setToolTip(
                f"会话名: {name}\n"
                f"chat_id: {chat_id}\n"
                f"owner_id: {owner_id}\n"
                f"类型: 群聊\n"
                f"描述: {description}\n"
                f"成员数: {member_count}"
            )
            self.chat_list.addItem(item)

            # 缓存
            chat["_resolved_chat_mode"] = chat_mode
            self._chat_data_cache[chat_id] = chat

            # 异步加载头像
            if avatar_url:
                self._load_chat_avatar(avatar_url, chat_id)

        # ── 第二轮：添加去重后的单聊联系人区域 ──
        if all_owner_ids:
            # 分隔线
            separator = QListWidgetItem("──── 单聊联系人 ────")
            separator.setFlags(Qt.NoItemFlags)  # 不可点击
            separator.setForeground(QColor("#999"))
            font = QFont()
            font.setBold(True)
            font.setPointSize(10)
            separator.setFont(font)
            self.chat_list.addItem(separator)

            for oid, info in all_owner_ids.items():
                display_text = f"👤 {oid}"
                item = QListWidgetItem(display_text)
                # 以 owner_id 作为数据，后面点击时走 open_id 发送模式
                item.setData(Qt.UserRole, oid)
                item.setData(Qt.UserRole + 1, oid)
                item.setData(Qt.UserRole + 2, "p2p")  # 标记为单聊联系人
                item.setToolTip(
                    f"open_id: {oid}\n"
                    f"来源会话: {info['first_chat_name']}\n"
                    f"💡 点击自动获取单聊会话并加载历史消息"
                )
                self.chat_list.addItem(item)

                # 缓存到 p2p 联系人
                self._p2p_contacts[oid] = {
                    "owner_id": oid,
                    "name": oid,
                    "chat_id": None,  # 尚无 p2p chat_id
                }

        unique_contacts = len(self._p2p_contacts)
        self.left_status.setText(
            f"已加载 {len(chats)} 个会话, "
            f"单聊联系人 {unique_contacts} 个 (从 owner_id 去重)"
        )
        self.load_chats_btn.setEnabled(True)

    def _load_chat_avatar(self, url: str, chat_id: str):
        """异步加载会话头像"""
        request = QNetworkRequest(QUrl(url))
        reply = self._net_manager.get(request)
        reply.finished.connect(lambda: self._on_avatar_loaded(reply, chat_id))

    def _on_avatar_loaded(self, reply: QNetworkReply, chat_id: str):
        """头像下载完成，设置到对应的列表项"""
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                icon = QIcon(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self._avatar_cache[chat_id] = icon
                # 找到对应的列表项并设置图标
                for i in range(self.chat_list.count()):
                    item = self.chat_list.item(i)
                    if item and item.data(Qt.UserRole) == chat_id:
                        item.setIcon(icon)
                        break
        reply.deleteLater()

    def _filter_chat_list(self, *_args):
        """搜索并按类型过滤会话列表"""
        text = self.search_input.text().strip().lower()
        type_filter = self.chat_type_filter.currentIndex()  # 0=全部, 1=群聊, 2=单聊

        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)

            # 分隔线：跟随单聊联系人的可见性
            if item.flags() == Qt.NoItemFlags:
                item.setHidden(type_filter == 1)  # 群聊模式下隐藏分隔线
                continue

            chat_mode = item.data(Qt.UserRole + 2) or ""
            visible = True

            # 文本过滤
            if text and text not in item.text().lower():
                visible = False

            # 类型过滤
            if type_filter == 1 and chat_mode == "p2p":
                visible = False  # 群聊模式下隐藏单聊联系人
            elif type_filter == 2 and chat_mode != "p2p":
                visible = False  # 单聊模式下隐藏群聊

            item.setHidden(not visible)

    def _on_chat_selected(self, item):
        """选择一个会话"""
        if not item or item.flags() == Qt.NoItemFlags:
            return  # 分隔线不可点击

        item_id = item.data(Qt.UserRole)
        chat_name = item.data(Qt.UserRole + 1)
        chat_type = item.data(Qt.UserRole + 2) or ""

        if chat_type == "p2p":
            # 单聊联系人：item_id 是 owner_id (open_id)
            self._open_p2p_chat_for_user(item_id)
        else:
            # 群聊：item_id 是 chat_id
            self._open_chat(item_id, chat_name)

    def _on_manual_open(self):
        """手动输入 ID 打开会话"""
        raw_id = self.manual_id_input.text().strip()
        if not raw_id:
            QMessageBox.warning(self, "提示", "请输入 ID")
            return

        type_index = self.receive_type_combo.currentIndex()
        type_map = {0: "chat_id", 1: "open_id", 2: "user_id", 3: "email"}
        id_type = type_map.get(type_index, "chat_id")

        # 自动检测 ID 类型（覆盖下拉选择）
        auto_type = self._auto_detect_id_type(raw_id)
        if auto_type:
            id_type = auto_type

        if id_type == "chat_id":
            # chat_id 直接打开会话并加载历史
            self._open_chat_with_info(raw_id)
        elif id_type == "open_id":
            # open_id 类型：先尝试发送消息获取 chat_id，再加载历史
            self._open_p2p_chat_for_user(raw_id)
        else:
            # 其他类型（user_id / email）：仅支持发送，不加载历史
            self._current_chat_id = raw_id
            self._current_chat_name = f"{id_type}: {raw_id[:16]}..."
            self._current_id_type = id_type
            self.chat_title_label.setText(f"📨 {self._current_chat_name}")
            self.chat_display.clear()
            self.chat_display.setPlaceholderText(
                f"已选择 {id_type} 类型的接收者: {raw_id}\n\n"
                "提示：该类型无法直接加载历史消息，但可以发送消息。\n"
                "发送消息后系统将自动获取 chat_id 并加载历史记录。"
            )
            self.send_btn.setEnabled(True)
            self.refresh_btn.setEnabled(False)
            self.status_label.setText(f"已选择 {id_type}: {raw_id}")

    def _open_chat_with_info(self, chat_id: str):
        """
        通过 chat_id 打开会话，先获取会话信息确定名称和类型。
        """
        if not self._messages_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.status_label.setText("正在获取会话信息...")
        self.manual_open_btn.setEnabled(False)

        def fetch_info():
            info = self._messages_api.get_chat_info(chat_id)
            return info

        worker = ApiWorker(fetch_info)
        worker.finished.connect(lambda result: self._on_chat_info_loaded(result, chat_id))
        worker.error.connect(lambda err: self._on_chat_info_error(err, chat_id))
        self._start_new_worker(worker)

    def _on_chat_info_loaded(self, result, chat_id: str):
        """会话信息加载完成"""
        self.manual_open_btn.setEnabled(True)
        data = result.get("data", {})
        chat_mode = data.get("chat_mode", "")
        name = data.get("name", "")

        if chat_mode == "p2p":
            display_name = f"👤 {name}" if name else f"👤 单聊 {chat_id[:12]}..."
        else:
            member_count = data.get("user_count", "")
            display_name = f"👥 {name}" if name else f"👥 群聊 {chat_id[:12]}..."
            if member_count:
                display_name += f" ({member_count}人)"

        self._open_chat(chat_id, display_name)

    def _on_chat_info_error(self, error_msg: str, chat_id: str):
        """获取会话信息失败时，仍尝试打开"""
        self.manual_open_btn.setEnabled(True)
        self.status_label.setText(f"获取会话信息失败，尝试直接加载消息...")
        self._open_chat(chat_id, f"会话 {chat_id[:12]}...")

    def _open_p2p_chat_for_user(self, open_id: str):
        """
        通过 open_id 打开单聊会话。
        策略：先从联系人缓存中查找已有的 p2p chat_id（O(1) 查找），
        找不到则自动发送一条临时消息获取 chat_id，然后撤回该消息并加载历史。
        """
        if not self._messages_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        # 从联系人缓存中查找 (O(1))
        contact = self._p2p_contacts.get(open_id)
        if contact and contact.get("chat_id"):
            # 已有 p2p chat_id，直接打开
            chat_id = contact["chat_id"]
            name = contact.get("name", "") or f"用户 {open_id[:12]}..."
            self.status_label.setText(
                f"✅ 已找到单聊会话 (chat_id: {chat_id[:16]}...)"
            )
            self._open_chat(chat_id, f"👤 {name}")
            return

        # 没有 p2p chat_id，自动发送临时消息获取 chat_id 并撤回
        self._send_temp_and_load_history(open_id)

    def _send_temp_and_load_history(self, open_id: str):
        """
        弹出对话框让用户选择发送方式，发送消息获取 chat_id，然后加载历史记录。
        用户可以选择"发送消息"（保留消息）或"发送并撤回"（发送后立即撤回）。
        """
        # 弹出选择对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("获取单聊会话")
        dialog.setMinimumWidth(400)
        dlg_layout = QVBoxLayout(dialog)

        # 说明文字
        info_label = QLabel(
            f"需要向用户 {open_id[:20]}... 发送一条消息以获取会话 ID。\n"
            "请编辑消息内容，并选择发送方式："
        )
        info_label.setWordWrap(True)
        dlg_layout.addWidget(info_label)

        # 消息内容输入框（可编辑）
        dlg_layout.addWidget(QLabel("消息内容:"))
        msg_edit = QTextEdit()
        msg_edit.setMaximumHeight(80)
        msg_edit.setPlainText("✅ New session started · model: vendor-claude-opus-4-5/aws-claude-opus-4-5")
        msg_edit.setPlaceholderText("输入要发送的消息内容...")
        dlg_layout.addWidget(msg_edit)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        send_keep_btn = QPushButton("📤 发送消息")
        send_keep_btn.setToolTip("发送消息并保留，获取会话 ID 后加载历史")
        send_keep_btn.setDefault(True)
        send_keep_btn.setStyleSheet(
            "QPushButton { background: #1677ff; color: white; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background: #4096ff; }"
        )
        btn_layout.addWidget(send_keep_btn)

        send_recall_btn = QPushButton("📤 发送并撤回")
        send_recall_btn.setToolTip("发送消息获取会话 ID 后立即撤回该消息")
        send_recall_btn.setStyleSheet(
            "QPushButton { background: #faad14; color: white; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background: #ffc53d; }"
        )
        btn_layout.addWidget(send_recall_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(
            "QPushButton { border: 1px solid #ddd; border-radius: 4px; padding: 8px 16px; }"
            "QPushButton:hover { background: #f0f0f0; }"
        )
        btn_layout.addWidget(cancel_btn)

        dlg_layout.addLayout(btn_layout)

        # 用于存储用户选择结果
        dialog._user_choice = None  # "send" | "recall" | None

        def on_send_keep():
            dialog._user_choice = "send"
            dialog.accept()

        def on_send_recall():
            dialog._user_choice = "recall"
            dialog.accept()

        send_keep_btn.clicked.connect(on_send_keep)
        send_recall_btn.clicked.connect(on_send_recall)
        cancel_btn.clicked.connect(dialog.reject)

        if dialog.exec() != QDialog.Accepted or not dialog._user_choice:
            return  # 用户取消

        msg_content = msg_edit.toPlainText().strip()
        if not msg_content:
            msg_content = " "  # 至少发送一个空格

        recall_after = dialog._user_choice == "recall"

        # 开始发送
        self._current_chat_id = open_id
        self._current_chat_name = f"用户 {open_id[:16]}..."
        self._current_id_type = "open_id"
        self._pending_recall = recall_after
        self._pending_msg_content = msg_content
        self.chat_title_label.setText(f"📨 {self._current_chat_name}")
        self.chat_display.clear()
        self.send_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        action_text = "发送并撤回" if recall_after else "发送消息"
        self.status_label.setText(f"正在{action_text}以获取单聊会话 ID...")

        worker = ApiWorker(
            self._messages_api.send_text_message, open_id, msg_content, "open_id"
        )
        worker.finished.connect(lambda result: self._on_temp_msg_sent(result, open_id))
        worker.error.connect(self._on_api_error)
        self._start_new_worker(worker)

    def _on_temp_msg_sent(self, result, open_id: str):
        """消息发送成功，获取 chat_id，根据用户选择决定是否撤回"""
        data = result.get("data", {})
        msg_id = data.get("message_id", "")
        chat_id = data.get("chat_id", "")

        if not chat_id:
            self.status_label.setText("❌ 未能获取 chat_id，请尝试手动发送消息")
            self.send_btn.setEnabled(True)
            return

        # 更新联系人缓存中的 chat_id
        if open_id in self._p2p_contacts:
            self._p2p_contacts[open_id]["chat_id"] = chat_id

        recall_after = getattr(self, '_pending_recall', True)

        if recall_after and msg_id:
            # 用户选择了"发送并撤回"
            self.status_label.setText(f"已获取 chat_id，正在撤回消息...")
            worker = ApiWorker(self._messages_api.delete_message, msg_id)
            worker.finished.connect(lambda _res: self._on_temp_msg_done(chat_id, open_id, recalled=True))
            worker.error.connect(lambda _err: self._on_temp_msg_done(chat_id, open_id, recalled=False))
            self._start_new_worker(worker)
        else:
            # 用户选择了"发送消息"（保留），直接加载历史
            self._on_temp_msg_done(chat_id, open_id, recalled=False)

    def _on_temp_msg_done(self, chat_id: str, open_id: str, recalled: bool = False):
        """消息处理完成（发送/撤回），打开会话并加载历史"""
        name = f"用户 {open_id[:16]}..."
        contact = self._p2p_contacts.get(open_id)
        if contact and contact.get("name"):
            name = contact["name"]

        action_desc = "已撤回消息" if recalled else "已发送消息"
        self.status_label.setText(
            f"✅ {action_desc}，获取单聊会话 (chat_id: {chat_id[:16]}...)"
        )
        self._open_chat(chat_id, f"👤 {name}")

    def _open_chat(self, chat_id: str, chat_name: str):
        """打开一个聊天会话"""
        self._current_chat_id = chat_id
        self._current_chat_name = chat_name
        self._current_id_type = "chat_id"
        self.chat_title_label.setText(f"💬 {chat_name}")
        self.send_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.manual_id_input.setText(chat_id)
        self.receive_type_combo.setCurrentIndex(0)

        # 加载历史消息
        self._load_messages()

    def _load_messages(self):
        """加载当前会话的历史消息"""
        if not self._messages_api or not self._current_chat_id:
            return

        if getattr(self, '_current_id_type', 'chat_id') != "chat_id":
            return

        self.status_label.setText("正在加载历史消息...")
        self.refresh_btn.setEnabled(False)

        worker = ApiWorker(
            self._messages_api.get_all_chat_messages,
            self._current_chat_id,
            max_count=100,
        )
        worker.finished.connect(self._on_messages_loaded)
        worker.error.connect(self._on_api_error)
        self._start_new_worker(worker)

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "<br/>")
        )

    def _format_message_html(self, time_str: str, sender_display: str, text: str, is_app: bool = False) -> str:
        """将单条消息格式化为 HTML 片段"""
        escaped_text = self._escape_html(text)
        sender_color = "#1677ff" if is_app else "#333"
        return (
            f'<div style="margin-bottom:10px;">'
            f'  <div style="font-size:11px; color:#999;">{self._escape_html(time_str)}</div>'
            f'  <div style="font-size:13px; font-weight:bold; color:{sender_color}; margin:2px 0;">'
            f'    {self._escape_html(sender_display)}'
            f'  </div>'
            f'  <div style="font-size:13px; color:#333; line-height:1.6; padding-left:4px;">'
            f'    {escaped_text}'
            f'  </div>'
            f'</div>'
        )

    def _on_messages_loaded(self, messages):
        """历史消息加载完成"""
        self.chat_display.clear()
        self.refresh_btn.setEnabled(True)

        if not messages:
            self.chat_display.setPlainText("（暂无消息记录）")
            self.status_label.setText(f"会话 [{self._current_chat_name}] 暂无消息")
            return

        html_parts = [
            '<div style="font-family: -apple-system, \'Segoe UI\', \'PingFang SC\', '
            '\'Microsoft YaHei\', sans-serif;">'
        ]

        # 按时间正序显示
        for msg in messages:
            sender = msg.get("sender", {})
            sender_type = sender.get("sender_type", "")
            sender_id = sender.get("id", "未知")
            create_time = msg.get("create_time", "")

            # 时间戳转可读时间（固定 UTC+8 中国时间）
            time_str = ""
            if create_time:
                try:
                    ts_val = int(create_time)
                    # 自动判断秒级(10位)或毫秒级(13位)时间戳
                    if ts_val > 1e12:
                        ts_val = ts_val / 1000  # 毫秒 -> 秒
                    cn_tz = timezone(timedelta(hours=8))
                    dt = datetime.fromtimestamp(ts_val, tz=cn_tz)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, OSError):
                    time_str = create_time

            # 发送者显示
            is_app = sender_type == "app"
            if is_app:
                sender_display = "🤖 应用"
            else:
                sender_display = f"👤 {sender_id[:12]}..."

            # 消息内容
            text = _parse_msg_content(msg)

            html_parts.append(self._format_message_html(time_str, sender_display, text, is_app))

        html_parts.append('</div>')
        self.chat_display.setHtml("".join(html_parts))

        # 滚动到底部
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)

        self.status_label.setText(f"已加载 {len(messages)} 条消息 - {self._current_chat_name}")

    # ─── 消息类型切换 ─────────────────────

    def _on_msg_type_changed(self, index):
        """消息类型切换"""
        is_rich = index == 1
        self.title_label.setVisible(is_rich)
        self.title_input.setVisible(is_rich)

        placeholders = {
            0: "输入消息... (Ctrl+Enter 发送)",
            1: "输入富文本消息内容...\n支持多行，每行自动成为一个段落",
            2: "输入卡片消息 JSON...",
        }
        self.msg_input.setPlaceholderText(placeholders.get(index, ""))

    # ─── 发送消息 ─────────────────────

    def _auto_detect_id_type(self, receive_id: str) -> str | None:
        """根据 ID 前缀自动检测类型"""
        if receive_id.startswith("oc_"):
            return "chat_id"
        elif receive_id.startswith("ou_"):
            return "open_id"
        elif receive_id.startswith("on_"):
            return "union_id"
        elif "@" in receive_id:
            return "email"
        return None

    def _on_send(self):
        """发送消息"""
        if not self._messages_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        if not self._current_chat_id:
            QMessageBox.warning(self, "提示", "请先选择一个会话对象")
            return

        content = self.msg_input.toPlainText().strip()
        if not content:
            return

        receive_id = self._current_chat_id
        receive_id_type = getattr(self, '_current_id_type', 'chat_id')

        # 自动检测 ID 类型
        auto_type = self._auto_detect_id_type(receive_id)
        if auto_type:
            receive_id_type = auto_type

        msg_type_index = self.msg_type_combo.currentIndex()

        self.status_label.setText(f"正在发送...")
        self.send_btn.setEnabled(False)

        if msg_type_index == 0:
            # 文本消息
            worker = ApiWorker(
                self._messages_api.send_text_message, receive_id, content, receive_id_type
            )
        elif msg_type_index == 1:
            # 富文本消息
            title = self.title_input.text().strip()
            post_content = text_to_post(content, title)
            worker = ApiWorker(
                self._messages_api.send_rich_text_message, receive_id, post_content, receive_id_type
            )
        elif msg_type_index == 2:
            # 卡片消息
            try:
                card_content = json.loads(content)
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "JSON 格式错误", f"卡片内容 JSON 解析失败:\n{e}")
                self.send_btn.setEnabled(True)
                self.status_label.setText("就绪")
                return
            worker = ApiWorker(
                self._messages_api.send_interactive_message, receive_id, card_content, receive_id_type
            )

        worker.finished.connect(self._on_send_result)
        worker.error.connect(self._on_api_error)
        self._start_new_worker(worker)

    def _on_send_result(self, result):
        """发送结果"""
        self.send_btn.setEnabled(True)
        data = result.get("data", {})
        msg_id = data.get("message_id", "未知")
        response_chat_id = data.get("chat_id", "")

        # 在聊天框中以 HTML 格式追加发送的消息
        content = self.msg_input.toPlainText().strip()
        cn_tz = timezone(timedelta(hours=8))
        now_str = datetime.now(tz=cn_tz).strftime("%Y-%m-%d %H:%M:%S")
        msg_html = self._format_message_html(now_str, "🤖 我（应用）", content, is_app=True)
        # 移动到末尾并插入 HTML
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertHtml(msg_html)

        # 滚动到底部
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)

        # 清空输入框
        self.msg_input.clear()

        self.status_label.setText(f"✅ 发送成功 (ID: {msg_id[:16]}...)")

        # 如果当前不是 chat_id 模式，但响应中返回了 chat_id，
        # 自动切换为 chat_id 模式并加载历史消息
        current_id_type = getattr(self, '_current_id_type', 'chat_id')
        if current_id_type != "chat_id" and response_chat_id:
            # 保存当前 open_id 用于更新缓存
            prev_open_id = self._current_chat_id

            self.status_label.setText(
                f"✅ 发送成功 - 已获取单聊会话 ID: {response_chat_id[:16]}..."
            )
            # 切换到 chat_id 模式
            self._current_chat_id = response_chat_id
            self._current_id_type = "chat_id"
            self._current_chat_name = f"👤 单聊 {response_chat_id[:12]}..."
            self.chat_title_label.setText(f"💬 {self._current_chat_name}")
            self.manual_id_input.setText(response_chat_id)
            self.receive_type_combo.setCurrentIndex(0)
            self.refresh_btn.setEnabled(True)

            # 更新联系人缓存中的 chat_id（下次点击可直接加载历史）
            if prev_open_id and prev_open_id in self._p2p_contacts:
                self._p2p_contacts[prev_open_id]["chat_id"] = response_chat_id

            # 自动加载历史消息（延迟 500ms 让 UI 更新）
            QTimer.singleShot(500, self._load_messages)

    # ─── 错误处理 ─────────────────────

    def _on_api_error(self, error_msg):
        """API 调用出错"""
        self.send_btn.setEnabled(True)
        self.load_chats_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.manual_open_btn.setEnabled(True)
        self.status_label.setText(f"❌ 错误: {error_msg}")
        QMessageBox.critical(self, "操作失败", error_msg)
