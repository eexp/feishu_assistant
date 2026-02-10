"""文档 Tab：文档列表 + 内容预览"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QSplitter,
    QLabel,
    QComboBox,
    QMessageBox,
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


# 文档类型图标映射
DOC_TYPE_ICONS = {
    "doc": "📝",
    "docx": "📝",
    "sheet": "📊",
    "bitable": "📋",
    "mindnote": "🧠",
    "folder": "📁",
    "file": "📄",
    "slides": "📽️",
    "wiki": "📚",
}


class DocumentsTab(QWidget):
    """文档管理 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._documents_api = None
        self._worker = None
        self._current_files = []
        self._folder_stack = []  # 文件夹导航栈
        self._setup_ui()

    def set_api(self, documents_api):
        """设置 API 实例"""
        self._documents_api = documents_api

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 顶部操作区 ---
        top_layout = QHBoxLayout()

        self.back_btn = QPushButton("⬅ 返回上级")
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setEnabled(False)
        top_layout.addWidget(self.back_btn)

        self.path_label = QLabel("根目录")
        top_layout.addWidget(self.path_label, 1)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("过滤文件名...")
        self.search_input.textChanged.connect(self._filter_files)
        top_layout.addWidget(self.search_input)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._load_files)
        top_layout.addWidget(self.refresh_btn)

        layout.addLayout(top_layout)

        # --- 主体区：左侧文件列表 + 右侧预览 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：文件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("文件列表"))

        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self._on_file_clicked)
        self.file_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        left_layout.addWidget(self.file_list)

        # 右侧：文档预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.doc_info_label = QLabel("文档信息")
        right_layout.addWidget(self.doc_info_label)

        self.doc_preview = QTextEdit()
        self.doc_preview.setReadOnly(True)
        self.doc_preview.setPlaceholderText("选择文档后在此预览内容...\n\n单击文件查看信息\n双击文件夹进入")
        right_layout.addWidget(self.doc_preview)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # --- 状态栏 ---
        self.status_label = QLabel("就绪 - 请先认证后刷新文件列表")
        layout.addWidget(self.status_label)

    def _load_files(self, folder_token: str = ""):
        """加载文件列表"""
        if not self._documents_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.status_label.setText("正在加载文件列表...")
        self.refresh_btn.setEnabled(False)

        self._worker = ApiWorker(self._documents_api.get_all_files, folder_token)
        self._worker.finished.connect(self._on_files_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_files_loaded(self, files):
        """文件列表加载完成"""
        self._current_files = files
        self._display_files(files)
        self.status_label.setText(f"已加载 {len(files)} 个文件")
        self.refresh_btn.setEnabled(True)

    def _display_files(self, files):
        """显示文件列表"""
        self.file_list.clear()

        for f in files:
            name = f.get("name", "未命名")
            file_type = f.get("type", "file")
            icon = DOC_TYPE_ICONS.get(file_type, "📄")

            item = QListWidgetItem(f"{icon}  {name}")
            item.setData(Qt.UserRole, f)
            item.setToolTip(
                f"名称: {name}\n"
                f"类型: {file_type}\n"
                f"Token: {f.get('token', '')}\n"
                f"创建时间: {f.get('created_time', '')}\n"
                f"修改时间: {f.get('modified_time', '')}"
            )
            self.file_list.addItem(item)

    def _filter_files(self, text):
        """过滤文件列表"""
        if not text:
            self._display_files(self._current_files)
            return

        text_lower = text.lower()
        filtered = [f for f in self._current_files if text_lower in f.get("name", "").lower()]
        self._display_files(filtered)

    def _on_file_clicked(self, item):
        """单击文件 - 显示信息"""
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return

        name = file_data.get("name", "未命名")
        file_type = file_data.get("type", "")
        token = file_data.get("token", "")
        url = file_data.get("url", "")

        info_text = (
            f"📄 文档信息\n"
            f"{'=' * 40}\n"
            f"名称: {name}\n"
            f"类型: {file_type}\n"
            f"Token: {token}\n"
            f"URL: {url}\n"
            f"创建时间: {file_data.get('created_time', 'N/A')}\n"
            f"修改时间: {file_data.get('modified_time', 'N/A')}\n"
            f"所有者: {file_data.get('owner_id', 'N/A')}\n"
        )
        self.doc_info_label.setText(f"文档: {name}")
        self.doc_preview.setPlainText(info_text)

        # 如果是 docx 类型，自动加载内容
        if file_type in ("docx", "doc"):
            self._load_document_content(token)

    def _on_file_double_clicked(self, item):
        """双击文件 - 如果是文件夹则进入"""
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return

        file_type = file_data.get("type", "")
        token = file_data.get("token", "")
        name = file_data.get("name", "")

        if file_type == "folder":
            self._folder_stack.append({"token": token, "name": name})
            self._update_path_label()
            self.back_btn.setEnabled(True)
            self._load_files(token)
        elif file_type in ("docx", "doc"):
            self._load_document_content(token)

    def _go_back(self):
        """返回上级文件夹"""
        if self._folder_stack:
            self._folder_stack.pop()
            self._update_path_label()
            self.back_btn.setEnabled(len(self._folder_stack) > 0)

            folder_token = self._folder_stack[-1]["token"] if self._folder_stack else ""
            self._load_files(folder_token)

    def _update_path_label(self):
        """更新路径显示"""
        if not self._folder_stack:
            self.path_label.setText("根目录")
        else:
            path = " > ".join([f["name"] for f in self._folder_stack])
            self.path_label.setText(f"根目录 > {path}")

    def _load_document_content(self, document_id: str):
        """加载文档内容"""
        self.status_label.setText("正在加载文档内容...")
        self.doc_preview.setPlainText("加载中...")

        self._worker = ApiWorker(self._documents_api.get_document_raw_content, document_id)
        self._worker.finished.connect(self._on_document_content_loaded)
        self._worker.error.connect(self._on_content_error)
        self._worker.start()

    def _on_document_content_loaded(self, result):
        """文档内容加载完成"""
        content = result.get("data", {}).get("content", "")
        if content:
            self.doc_preview.setPlainText(content)
            self.status_label.setText("文档内容加载完成")
        else:
            self.doc_preview.setPlainText("（文档内容为空或无法解析）")
            self.status_label.setText("文档内容为空")

    def _on_content_error(self, error_msg):
        """文档内容加载失败"""
        self.doc_preview.setPlainText(f"加载失败: {error_msg}")
        self.status_label.setText(f"错误: {error_msg}")

    def _on_api_error(self, error_msg):
        """API 调用出错"""
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "API 错误", error_msg)
