"""飞书助手 - 入口文件"""

import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from ui.main_window import MainWindow


def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容 PyInstaller 打包和开发环境"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def main():
    app = QApplication(sys.argv)

    # 设置应用图标
    icon_path = resource_path(os.path.join('images', 'iconfeishuLOGO.png'))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 设置全局字体
    font = QFont()
    font.setPointSize(12)
    app.setFont(font)

    # 设置应用样式
    app.setStyle("Fusion")

    # 设置全局样式表
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ccc;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        QPushButton {
            padding: 4px 10px;
            border: 1px solid #c8c8c8;
            border-radius: 4px;
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fafafa, stop:1 #f0f0f0);
        }
        QPushButton:hover {
            border-color: #aaa;
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0f0f0, stop:1 #e6e6e6);
        }
        QPushButton:pressed {
            background-color: #e0e0e0;
        }
        QPushButton:disabled {
            color: #aaa;
            border-color: #ddd;
        }
        QTabWidget::pane {
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        QTableWidget {
            gridline-color: #e0e0e0;
            alternate-background-color: #f5f5f5;
        }
        QTreeWidget {
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        QListWidget {
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        QTextEdit {
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        QLineEdit {
            padding: 4px 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        QLineEdit:focus {
            border-color: #4a90d9;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
