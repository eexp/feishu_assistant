"""消息 Tab：左侧选择消息对象 + 右侧聊天框与发送"""

import json
import time
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
        self._current_chat_id = None
        self._current_chat_name = ""
        self._chat_data_cache = {}  # chat_id -> chat info
        self._avatar_cache = {}  # chat_id -> QIcon
        self._net_manager = QNetworkAccessManager(self)
        self._setup_ui()

    def set_api(self, messages_api):
        """设置 API 实例"""
        self._messages_api = messages_api

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

        self._worker = ApiWorker(self._messages_api.get_all_chats)
        self._worker.finished.connect(self._on_chats_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_chats_loaded(self, chats):
        """会话列表加载完成"""
        self.chat_list.clear()
        self._chat_data_cache.clear()

        p2p_count = 0
        group_count = 0

        for chat in chats:
            name = chat.get("name", "未命名会话")
            chat_id = chat.get("chat_id", "")
            # chat_mode / chat_type 可能在不同 API 版本中字段不同
            chat_mode = chat.get("chat_mode", "") or chat.get("chat_type", "")
            description = chat.get("description", "")
            owner_id = chat.get("owner_id", "")
            member_count = chat.get("user_count", "") or chat.get("member_count", "")
            avatar_url = chat.get("avatar", "")

            # 图标和标签区分群聊和单聊
            if chat_mode == "p2p":
                p2p_count += 1
                if not name or name == "未命名会话":
                    name = f"用户 {owner_id[:12]}..." if owner_id else "未命名单聊"
                display_text = f"👤 {name}"
            else:
                if not chat_mode:
                    chat_mode = "group"  # 默认为群聊
                group_count += 1
                display_text = f"👥 {name}"
                if member_count:
                    display_text += f" ({member_count}人)"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, chat_id)
            item.setData(Qt.UserRole + 1, name)
            item.setData(Qt.UserRole + 2, chat_mode)  # 存储会话类型用于过滤
            item.setToolTip(
                f"会话名: {name}\n"
                f"ID: {chat_id}\n"
                f"类型: {'单聊' if chat_mode == 'p2p' else '群聊'}\n"
                f"描述: {description}\n"
                f"成员数: {member_count}"
            )
            self.chat_list.addItem(item)

            # 缓存 chat_mode 到 chat 数据中（方便后续使用）
            chat["_resolved_chat_mode"] = chat_mode
            self._chat_data_cache[chat_id] = chat

            # 异步加载头像
            if avatar_url:
                self._load_chat_avatar(avatar_url, chat_id)

        self.left_status.setText(
            f"已加载 {len(chats)} 个会话 (群聊 {group_count}, 单聊 {p2p_count})"
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
            chat_mode = item.data(Qt.UserRole + 2) or ""
            visible = True

            # 文本过滤
            if text and text not in item.text().lower():
                visible = False

            # 类型过滤
            if type_filter == 1 and chat_mode == "p2p":
                visible = False  # 群聊模式下隐藏单聊
            elif type_filter == 2 and chat_mode != "p2p":
                visible = False  # 单聊模式下隐藏群聊

            item.setHidden(not visible)

    def _on_chat_selected(self, item):
        """选择一个会话"""
        chat_id = item.data(Qt.UserRole)
        chat_name = item.data(Qt.UserRole + 1)
        self._open_chat(chat_id, chat_name)

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
            self._open_chat(raw_id, f"会话 {raw_id[:12]}...")
        elif id_type == "open_id":
            # open_id 类型：尝试从已加载的会话列表中查找对应的单聊
            self._find_p2p_chat_for_user(raw_id)
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
                "如需查看历史消息，请使用 chat_id 或 open_id。"
            )
            self.send_btn.setEnabled(True)
            self.refresh_btn.setEnabled(False)
            self.status_label.setText(f"已选择 {id_type}: {raw_id}")

    def _find_p2p_chat_for_user(self, open_id: str):
        """
        根据用户 open_id 查找对应的单聊会话。
        遍历所有已加载的会话，逐个检查成员是否匹配。
        """
        if not self._messages_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        if not self._chat_data_cache:
            # 还没加载过会话列表，提示用户
            QMessageBox.information(
                self, "提示",
                "请先点击「加载会话列表」获取会话数据，\n然后再通过 open_id 查找单聊会话。"
            )
            return

        # 获取所有会话 ID（优先搜索 p2p 类型，再搜索其他类型）
        all_chat_ids = list(self._chat_data_cache.keys())
        # 把 p2p 类型排前面优先搜索
        all_chat_ids.sort(
            key=lambda cid: 0 if self._chat_data_cache[cid].get("_resolved_chat_mode") == "p2p" else 1
        )

        self.status_label.setText("正在查找用户单聊会话...")
        self.manual_open_btn.setEnabled(False)

        def search_chats():
            """在后台线程中逐个检查会话的成员"""
            for chat_id in all_chat_ids:
                try:
                    members = self._messages_api.get_all_chat_members(chat_id)
                    for member in members:
                        if member.get("member_id") == open_id:
                            chat_info = self._chat_data_cache.get(chat_id, {})
                            member_name = member.get("name", "")
                            chat_name = chat_info.get("name", "") or member_name or "会话"
                            return {
                                "chat_id": chat_id,
                                "name": chat_name,
                                "member_name": member_name,
                            }
                except Exception:
                    continue
            return None

        self._worker = ApiWorker(search_chats)
        self._worker.finished.connect(lambda result: self._on_p2p_found(result, open_id))
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_p2p_found(self, result, open_id: str):
        """查找单聊会话结果回调"""
        self.manual_open_btn.setEnabled(True)

        if result:
            chat_id = result["chat_id"]
            name = result.get("member_name") or result.get("name", "单聊")
            display_name = f"👤 {name}"
            self.status_label.setText(f"已找到用户 {name} 的单聊会话")
            self._open_chat(chat_id, display_name)
        else:
            # 没找到匹配的 p2p 会话，降级为仅发送模式
            self._set_open_id_send_only(open_id)
            self.status_label.setText("未找到匹配的单聊会话，已切换为发送模式")

    def _set_open_id_send_only(self, open_id: str):
        """将 open_id 设为仅发送模式（无法加载历史）"""
        self._current_chat_id = open_id
        self._current_chat_name = f"用户 {open_id[:16]}..."
        self._current_id_type = "open_id"
        self.chat_title_label.setText(f"📨 {self._current_chat_name}")
        self.chat_display.clear()
        self.chat_display.setPlaceholderText(
            f"已选择用户: {open_id}\n\n"
            "未在已加载的会话列表中找到与该用户的单聊记录。\n\n"
            "可能的原因：\n"
            "• 机器人尚未与该用户建立过单聊\n"
            "• 会话列表未加载或不完整\n\n"
            "当前仍可发送消息给该用户。发送消息后将自动建立单聊，\n"
            "重新加载会话列表即可查看历史消息。"
        )
        self.send_btn.setEnabled(True)
        self.refresh_btn.setEnabled(False)

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

        self._worker = ApiWorker(
            self._messages_api.get_all_chat_messages,
            self._current_chat_id,
            max_count=100,
        )
        self._worker.finished.connect(self._on_messages_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

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

            # 时间戳转可读时间
            time_str = ""
            if create_time:
                try:
                    ts = int(create_time) / 1000  # 毫秒 -> 秒
                    time_str = time.strftime("%m-%d %H:%M", time.localtime(ts))
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
            self._worker = ApiWorker(
                self._messages_api.send_text_message, receive_id, content, receive_id_type
            )
        elif msg_type_index == 1:
            # 富文本消息
            title = self.title_input.text().strip()
            post_content = text_to_post(content, title)
            self._worker = ApiWorker(
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

        # 在聊天框中以 HTML 格式追加发送的消息
        content = self.msg_input.toPlainText().strip()
        now_str = time.strftime("%m-%d %H:%M", time.localtime())
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

    # ─── 错误处理 ─────────────────────

    def _on_api_error(self, error_msg):
        """API 调用出错"""
        self.send_btn.setEnabled(True)
        self.load_chats_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.manual_open_btn.setEnabled(True)
        self.status_label.setText(f"❌ 错误: {error_msg}")
        QMessageBox.critical(self, "操作失败", error_msg)
