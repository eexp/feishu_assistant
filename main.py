"""飞书助手 - 入口文件"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

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
            padding: 5px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #e0e0e0;
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
