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
from PySide6.QtGui import QFont, QIcon

from api.auth import FeishuAuth
from api.contacts import ContactsAPI
from api.messages import MessagesAPI
from api.documents import DocumentsAPI
from ui.contacts_tab import ContactsTab
from ui.messages_tab import MessagesTab
from ui.documents_tab import DocumentsTab
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
    """认证异步线程"""

    success = Signal()
    error = Signal(str)

    def __init__(self, auth: FeishuAuth):
        super().__init__()
        self.auth = auth

    def run(self):
        try:
            self.auth.get_tenant_access_token()
            self.success.emit()
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
        auth_layout = QHBoxLayout(auth_group)

        # App ID
        auth_layout.addWidget(QLabel("App ID:"))
        self.app_id_input = QLineEdit()
        self.app_id_input.setPlaceholderText("输入飞书应用的 App ID")
        self.app_id_input.setMinimumWidth(200)
        auth_layout.addWidget(self.app_id_input)

        # App Secret（带内嵌显示/隐藏按钮）
        auth_layout.addWidget(QLabel("App Secret:"))
        self.app_secret_input = PasswordLineEdit()
        self.app_secret_input.setPlaceholderText("输入飞书应用的 App Secret")
        self.app_secret_input.setMinimumWidth(200)
        auth_layout.addWidget(self.app_secret_input)

        # 认证按钮
        self.auth_btn = QPushButton("🔗 认证")
        self.auth_btn.setMinimumWidth(80)
        self.auth_btn.clicked.connect(self._on_authenticate)
        auth_layout.addWidget(self.auth_btn)

        # 保存按钮
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setToolTip("保存凭证到本地")
        self.save_btn.clicked.connect(self._save_credentials)
        auth_layout.addWidget(self.save_btn)

        # 认证状态
        self.auth_status = QLabel("❌ 未认证")
        self.auth_status.setMinimumWidth(100)
        auth_layout.addWidget(self.auth_status)

        main_layout.addWidget(auth_group)

        # --- Tab 容器 ---
        self.tabs = QTabWidget()

        self.contacts_tab = ContactsTab()
        self.messages_tab = MessagesTab()
        self.documents_tab = DocumentsTab()
        self.permissions_tab = PermissionsTab()

        self.tabs.addTab(self.permissions_tab, "🔐 权限检测")
        self.tabs.addTab(self.contacts_tab, "👥 联系人")
        self.tabs.addTab(self.messages_tab, "💬 消息")
        self.tabs.addTab(self.documents_tab, "📄 文档")
        

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

    def _on_auth_success(self):
        """认证成功"""
        self.auth_btn.setEnabled(True)
        self.auth_status.setText("✅ 已认证")
        self.statusBar().showMessage("✅ 认证成功！可以开始使用各功能了")

        # 启用 Tab 并传入 API
        self.tabs.setEnabled(True)

        contacts_api = ContactsAPI(self._auth)
        messages_api = MessagesAPI(self._auth)
        documents_api = DocumentsAPI(self._auth)

        self.contacts_tab.set_api(contacts_api)
        self.messages_tab.set_api(messages_api)
        self.documents_tab.set_api(documents_api)
        self.permissions_tab.set_auth(self._auth)

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
