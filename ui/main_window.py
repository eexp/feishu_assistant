"""主窗口：凭证输入区 + Tab 容器"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QTabWidget,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QStatusBar,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from api.auth import FeishuAuth
from api.contacts import ContactsAPI
from api.messages import MessagesAPI
from api.documents import DocumentsAPI
from api.sheets import SheetsAPI
from api.bitable import BitableAPI
from api.drive import DriveAPI
from api.calendar import CalendarAPI
from ui.contacts_tab import ContactsTab
from ui.messages_tab import MessagesTab
from ui.documents_tab import DocumentsTab
from ui.sheets_tab import SheetsTab
from ui.bitable_tab import BitableTab
from ui.drive_tab import DriveTab
from ui.calendar_tab import CalendarTab
from ui.permissions_tab import PermissionsTab
from utils.config_manager import get_credentials, save_credentials


class PasswordLineEdit(QLineEdit):
    """带内嵌显示/隐藏按钮的密码输入框，模仿网页密码框风格"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.Password)
        self._visible = False

        self._toggle_btn = QPushButton("显示", self)
        self._toggle_btn.setFixedSize(36, 20)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setToolTip("显示/隐藏密钥")
        self._toggle_btn.setStyleSheet(
            """
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 3px;
                background: #f5f5f5;
                color: #555;
                font-size: 11px;
                padding: 0 4px;
            }
            QPushButton:hover {
                background: #e8e8e8;
                color: #333;
                border-color: #999;
            }
            QPushButton:pressed {
                background: #ddd;
            }
            """
        )
        self._toggle_btn.clicked.connect(self._toggle_visibility)
        # 右侧留出按钮空间
        self.setTextMargins(0, 0, 42, 0)

    def _toggle_visibility(self):
        self._visible = not self._visible
        if self._visible:
            self.setEchoMode(QLineEdit.Normal)
            self._toggle_btn.setText("隐藏")
        else:
            self.setEchoMode(QLineEdit.Password)
            self._toggle_btn.setText("显示")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 将按钮定位到输入框右侧内部，垂直居中
        btn_x = self.width() - self._toggle_btn.width() - 4
        btn_y = (self.height() - self._toggle_btn.height()) // 2
        self._toggle_btn.move(btn_x, btn_y)


class AuthWorker(QThread):
    """认证异步线程，获取 token 并拉取机器人信息"""

    success = Signal(dict)  # bot_info dict
    error = Signal(str)

    def __init__(self, auth: FeishuAuth):
        super().__init__()
        self.auth = auth

    def run(self):
        try:
            self.auth.get_tenant_access_token()
            # 认证成功后获取机器人信息
            try:
                bot_info = self.auth.get_bot_info()
            except Exception:
                bot_info = {}
            self.success.emit(bot_info)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """飞书助手主窗口"""

    def __init__(self):
        super().__init__()
        self._auth = None
        self._auth_worker = None
        self._setup_ui()
        self._load_saved_credentials()

    def _setup_ui(self):
        self.setWindowTitle("飞书助手 - Feishu Assistant")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # --- 认证区域 ---
        auth_group = QGroupBox("🔐 飞书应用凭证")
        auth_group_layout = QVBoxLayout(auth_group)

        # 凭证输入行
        auth_input_layout = QHBoxLayout()

        # App ID
        auth_input_layout.addWidget(QLabel("App ID:"))
        self.app_id_input = QLineEdit()
        self.app_id_input.setPlaceholderText("输入飞书应用的 App ID")
        self.app_id_input.setMinimumWidth(200)
        auth_input_layout.addWidget(self.app_id_input)

        # App Secret（带内嵌显示/隐藏按钮）
        auth_input_layout.addWidget(QLabel("App Secret:"))
        self.app_secret_input = PasswordLineEdit()
        self.app_secret_input.setPlaceholderText("输入飞书应用的 App Secret")
        self.app_secret_input.setMinimumWidth(200)
        auth_input_layout.addWidget(self.app_secret_input)

        # 认证按钮
        self.auth_btn = QPushButton("🔗 认证")
        self.auth_btn.setMinimumWidth(80)
        self.auth_btn.clicked.connect(self._on_authenticate)
        auth_input_layout.addWidget(self.auth_btn)

        # 保存按钮
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setToolTip("保存凭证到本地")
        self.save_btn.clicked.connect(self._save_credentials)
        auth_input_layout.addWidget(self.save_btn)

        # 认证状态
        self.auth_status = QLabel("❌ 未认证")
        self.auth_status.setMinimumWidth(100)
        auth_input_layout.addWidget(self.auth_status)

        auth_group_layout.addLayout(auth_input_layout)

        # 机器人信息行（认证成功后显示）
        self.bot_info_widget = QWidget()
        bot_info_layout = QHBoxLayout(self.bot_info_widget)
        bot_info_layout.setContentsMargins(0, 4, 0, 0)

        self.bot_avatar_label = QLabel()
        self.bot_avatar_label.setFixedSize(32, 32)
        self.bot_avatar_label.setScaledContents(True)
        self.bot_avatar_label.setStyleSheet("border-radius: 4px;")
        bot_info_layout.addWidget(self.bot_avatar_label)

        self.bot_name_label = QLabel()
        self.bot_name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        bot_info_layout.addWidget(self.bot_name_label)

        self.bot_detail_label = QLabel()
        self.bot_detail_label.setStyleSheet("color: #666; font-size: 12px;")
        bot_info_layout.addWidget(self.bot_detail_label)

        bot_info_layout.addStretch()
        self.bot_info_widget.setVisible(False)
        auth_group_layout.addWidget(self.bot_info_widget)

        main_layout.addWidget(auth_group)

        # 用于异步加载头像的网络管理器
        self._net_manager = QNetworkAccessManager(self)

        # --- Tab 容器 ---
        self.tabs = QTabWidget()

        self.contacts_tab = ContactsTab()
        self.messages_tab = MessagesTab()
        self.documents_tab = DocumentsTab()
        self.sheets_tab = SheetsTab()
        self.bitable_tab = BitableTab()
        self.drive_tab = DriveTab()
        self.calendar_tab = CalendarTab()
        self.permissions_tab = PermissionsTab()

        self.tabs.addTab(self.permissions_tab, "🔐 权限检测")
        self.tabs.addTab(self.contacts_tab, "👥 联系人")
        self.tabs.addTab(self.messages_tab, "💬 消息")
        self.tabs.addTab(self.documents_tab, "📄 文档")
        self.tabs.addTab(self.sheets_tab, "📊 表格")
        self.tabs.addTab(self.bitable_tab, "📋 多维表格")
        self.tabs.addTab(self.drive_tab, "📁 云盘")
        self.tabs.addTab(self.calendar_tab, "📅 日历")

        # 初始禁用 Tab
        self.tabs.setEnabled(False)

        main_layout.addWidget(self.tabs)

        # --- 状态栏 ---
        self.statusBar().showMessage("请输入 App ID 和 App Secret 后点击认证")

    def _load_saved_credentials(self):
        """加载已保存的凭证"""
        app_id, app_secret = get_credentials()
        if app_id:
            self.app_id_input.setText(app_id)
        if app_secret:
            self.app_secret_input.setText(app_secret)

    def _save_credentials(self):
        """保存凭证到本地"""
        app_id = self.app_id_input.text().strip()
        app_secret = self.app_secret_input.text().strip()

        if not app_id or not app_secret:
            QMessageBox.warning(self, "提示", "请填写 App ID 和 App Secret")
            return

        save_credentials(app_id, app_secret)
        self.statusBar().showMessage("✅ 凭证已保存到本地")

    def _on_authenticate(self):
        """点击认证按钮"""
        app_id = self.app_id_input.text().strip()
        app_secret = self.app_secret_input.text().strip()

        if not app_id or not app_secret:
            QMessageBox.warning(self, "提示", "请填写 App ID 和 App Secret")
            return

        self.auth_btn.setEnabled(False)
        self.auth_status.setText("⏳ 认证中...")
        self.statusBar().showMessage("正在验证凭证...")

        self._auth = FeishuAuth(app_id, app_secret)
        self._auth_worker = AuthWorker(self._auth)
        self._auth_worker.success.connect(self._on_auth_success)
        self._auth_worker.error.connect(self._on_auth_error)
        self._auth_worker.start()

    def _on_auth_success(self, bot_info: dict):
        """认证成功，显示机器人信息"""
        self.auth_btn.setEnabled(True)
        self.auth_status.setText("✅ 已认证")
        self.statusBar().showMessage("✅ 认证成功！可以开始使用各功能了")

        # 显示机器人信息
        if bot_info:
            app_name = bot_info.get("app_name", "未知应用")
            open_id = bot_info.get("open_id", "")
            avatar_url = bot_info.get("avatar_url", "")

            self.bot_name_label.setText(f"🤖 {app_name}")
            self.bot_detail_label.setText(f"Open ID: {open_id}")
            self.bot_info_widget.setVisible(True)

            # 异步加载头像
            if avatar_url:
                self._load_bot_avatar(avatar_url)
        else:
            self.bot_info_widget.setVisible(False)

        # 启用 Tab 并传入 API
        self.tabs.setEnabled(True)

        contacts_api = ContactsAPI(self._auth)
        messages_api = MessagesAPI(self._auth)
        documents_api = DocumentsAPI(self._auth)
        sheets_api = SheetsAPI(self._auth)
        bitable_api = BitableAPI(self._auth)
        drive_api = DriveAPI(self._auth)
        calendar_api = CalendarAPI(self._auth)

        self.contacts_tab.set_api(contacts_api)
        self.messages_tab.set_api(messages_api)
        self.documents_tab.set_api(documents_api)
        self.sheets_tab.set_api(sheets_api)
        self.bitable_tab.set_api(bitable_api)
        self.drive_tab.set_api(drive_api)
        self.calendar_tab.set_api(calendar_api)
        self.permissions_tab.set_auth(self._auth)

    def _load_bot_avatar(self, url: str):
        """异步加载机器人头像"""
        from PySide6.QtCore import QUrl
        request = QNetworkRequest(QUrl(url))
        reply = self._net_manager.get(request)
        reply.finished.connect(lambda: self._on_avatar_loaded(reply))

    def _on_avatar_loaded(self, reply: QNetworkReply):
        """头像下载完成"""
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self.bot_avatar_label.setPixmap(
                    pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        reply.deleteLater()

    def _on_auth_error(self, error_msg):
        """认证失败"""
        self.auth_btn.setEnabled(True)
        self.auth_status.setText("❌ 认证失败")
        self.statusBar().showMessage(f"❌ 认证失败: {error_msg}")
        QMessageBox.critical(
            self,
            "认证失败",
            f"无法获取 tenant_access_token:\n\n{error_msg}\n\n请检查 App ID 和 App Secret 是否正确。",
        )
