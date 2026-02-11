"""日历 Tab：日历列表 + 日程管理 + 忙闲查询 + 空闲时段"""

import time as time_mod
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QLabel,
    QGroupBox,
    QHeaderView,
    QMessageBox,
    QDateEdit,
    QTimeEdit,
    QTextEdit,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QThread, Signal, QDate, QTime


class ApiWorker(QThread):
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


# 日历类型映射
CALENDAR_TYPE_LABELS = {
    "primary": "主日历",
    "shared": "共享日历",
    "google": "谷歌日历",
    "resource": "会议室日历",
    "exchange": "Exchange日历",
    "unknown": "未知",
}

# 角色映射
CALENDAR_ROLE_LABELS = {
    "owner": "管理员",
    "writer": "编辑者",
    "reader": "订阅者",
    "free_busy_reader": "游客",
    "unknown": "未知",
}


class CalendarTab(QWidget):
    """日历管理 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._calendar_api = None
        self._worker = None
        self._calendars = []  # 已加载的日历列表
        self._selected_calendar_id = ""
        self._setup_ui()

    def set_api(self, calendar_api):
        self._calendar_api = calendar_api

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 顶部：日历列表 ---
        cal_group = QGroupBox("📆 日历列表")
        cal_layout = QVBoxLayout(cal_group)

        cal_header = QHBoxLayout()
        self.load_calendars_btn = QPushButton("🔄 加载日历列表")
        self.load_calendars_btn.clicked.connect(self._load_calendars)
        cal_header.addWidget(self.load_calendars_btn)
        cal_header.addStretch()

        self.cal_info_label = QLabel("认证后点击加载日历列表")
        cal_header.addWidget(self.cal_info_label)
        cal_layout.addLayout(cal_header)

        # 日历列表下拉 + 详情
        cal_select_row = QHBoxLayout()
        cal_select_row.addWidget(QLabel("选择日历:"))
        self.calendar_combo = QComboBox()
        self.calendar_combo.setMinimumWidth(300)
        self.calendar_combo.currentIndexChanged.connect(self._on_calendar_selected)
        cal_select_row.addWidget(self.calendar_combo, 1)

        self.cal_detail_label = QLabel("")
        self.cal_detail_label.setStyleSheet("color: #666; font-size: 12px;")
        cal_select_row.addWidget(self.cal_detail_label)
        cal_layout.addLayout(cal_select_row)
        layout.addWidget(cal_group)

        # --- 主体区域 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：日程列表 + 创建日程
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 日程列表区
        list_group = QGroupBox("📋 日程列表")
        list_layout = QVBoxLayout(list_group)

        list_header = QHBoxLayout()
        list_header.addWidget(QLabel("日期:"))
        self.list_date_edit = QDateEdit()
        self.list_date_edit.setDate(QDate.currentDate())
        self.list_date_edit.setCalendarPopup(True)
        list_header.addWidget(self.list_date_edit)

        self.load_events_btn = QPushButton("🔄 加载日程")
        self.load_events_btn.clicked.connect(self._load_events)
        list_header.addWidget(self.load_events_btn)
        list_header.addStretch()
        list_layout.addLayout(list_header)

        self.events_table = QTableWidget()
        self.events_table.setColumnCount(5)
        self.events_table.setHorizontalHeaderLabels(["标题", "开始时间", "结束时间", "状态", "日程ID"])
        self.events_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.events_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.events_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.events_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.events_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.events_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.events_table.setAlternatingRowColors(True)
        list_layout.addWidget(self.events_table)
        left_layout.addWidget(list_group)

        # 创建日程区
        create_group = QGroupBox("➕ 创建日程")
        create_layout = QVBoxLayout(create_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("标题:"))
        self.summary_input = QLineEdit()
        self.summary_input.setPlaceholderText("日程标题/会议名称")
        row1.addWidget(self.summary_input, 1)
        create_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("日期:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        row2.addWidget(self.date_edit)

        row2.addWidget(QLabel("开始:"))
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setTime(QTime(10, 0))
        row2.addWidget(self.start_time_edit)

        row2.addWidget(QLabel("结束:"))
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setTime(QTime(11, 0))
        row2.addWidget(self.end_time_edit)

        self.video_check = QCheckBox("视频会议")
        self.video_check.setChecked(True)
        row2.addWidget(self.video_check)
        create_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("参会人:"))
        self.attendees_input = QLineEdit()
        self.attendees_input.setPlaceholderText("open_id 逗号分隔（可选）")
        row3.addWidget(self.attendees_input, 1)

        row3.addWidget(QLabel("描述:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("日程描述（可选）")
        row3.addWidget(self.desc_input, 1)
        create_layout.addLayout(row3)

        create_btn_row = QHBoxLayout()
        create_btn_row.addStretch()
        self.create_event_btn = QPushButton("✅ 创建日程")
        self.create_event_btn.clicked.connect(self._create_event)
        create_btn_row.addWidget(self.create_event_btn)
        create_layout.addLayout(create_btn_row)

        left_layout.addWidget(create_group)

        # 右侧：空闲时段查询
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        free_group = QGroupBox("🔍 空闲时段查询")
        free_layout = QVBoxLayout(free_group)

        free_row1 = QHBoxLayout()
        free_row1.addWidget(QLabel("用户 open_id:"))
        self.freebusy_users_input = QLineEdit()
        self.freebusy_users_input.setPlaceholderText("ou_xxx,ou_yyy（逗号分隔）")
        free_row1.addWidget(self.freebusy_users_input, 1)
        free_layout.addLayout(free_row1)

        free_row2 = QHBoxLayout()
        free_row2.addWidget(QLabel("日期:"))
        self.free_date_edit = QDateEdit()
        self.free_date_edit.setDate(QDate.currentDate())
        self.free_date_edit.setCalendarPopup(True)
        free_row2.addWidget(self.free_date_edit)

        free_row2.addWidget(QLabel("时间范围:"))
        self.start_hour_spin = QSpinBox()
        self.start_hour_spin.setRange(0, 23)
        self.start_hour_spin.setValue(9)
        free_row2.addWidget(self.start_hour_spin)
        free_row2.addWidget(QLabel("-"))
        self.end_hour_spin = QSpinBox()
        self.end_hour_spin.setRange(0, 23)
        self.end_hour_spin.setValue(18)
        free_row2.addWidget(self.end_hour_spin)

        free_row2.addWidget(QLabel("时长(分):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(15, 480)
        self.duration_spin.setValue(30)
        self.duration_spin.setSingleStep(15)
        free_row2.addWidget(self.duration_spin)

        self.find_free_btn = QPushButton("🔍 查找空闲")
        self.find_free_btn.clicked.connect(self._find_free_slots)
        free_row2.addWidget(self.find_free_btn)
        free_layout.addLayout(free_row2)

        right_layout.addWidget(free_group)

        # 空闲时段结果
        result_group = QGroupBox("🕐 空闲时段结果")
        result_layout = QVBoxLayout(result_group)
        self.free_slots_table = QTableWidget()
        self.free_slots_table.setColumnCount(3)
        self.free_slots_table.setHorizontalHeaderLabels(["开始", "结束", "时长(分)"])
        self.free_slots_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.free_slots_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.free_slots_table.setAlternatingRowColors(True)
        result_layout.addWidget(self.free_slots_table)
        right_layout.addWidget(result_group)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.status_label = QLabel("就绪 - 认证后点击「加载日历列表」开始使用")
        layout.addWidget(self.status_label)

    # ── 日历列表 ──────────────────────────

    def _load_calendars(self):
        if not self._calendar_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        self.status_label.setText("正在加载日历列表...")
        self.load_calendars_btn.setEnabled(False)
        self._worker = ApiWorker(self._calendar_api.get_all_calendars)
        self._worker.finished.connect(self._on_calendars_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_calendars_loaded(self, calendars):
        self.load_calendars_btn.setEnabled(True)
        self._calendars = calendars
        self.calendar_combo.clear()

        for cal in calendars:
            cal_id = cal.get("calendar_id", "")
            summary = cal.get("summary", "")
            cal_type = CALENDAR_TYPE_LABELS.get(cal.get("type", ""), cal.get("type", ""))
            role = CALENDAR_ROLE_LABELS.get(cal.get("role", ""), cal.get("role", ""))
            display = f"{summary}  [{cal_type}] ({role})"
            self.calendar_combo.addItem(display, cal_id)

        self.cal_info_label.setText(f"共 {len(calendars)} 个日历")
        self.status_label.setText(f"已加载 {len(calendars)} 个日历，请选择日历后操作")

    def _on_calendar_selected(self, index):
        if index < 0 or index >= len(self._calendars):
            self._selected_calendar_id = ""
            self.cal_detail_label.setText("")
            return

        cal = self._calendars[index]
        self._selected_calendar_id = cal.get("calendar_id", "")
        desc = cal.get("description", "") or "无描述"
        permissions = cal.get("permissions", "")
        self.cal_detail_label.setText(
            f"ID: {self._selected_calendar_id[:20]}...  |  权限: {permissions}  |  {desc}"
        )

    def _get_selected_calendar_id(self) -> str:
        """获取当前选中的日历 ID，未选择则返回空串"""
        idx = self.calendar_combo.currentIndex()
        if idx >= 0:
            return self.calendar_combo.itemData(idx) or ""
        return ""

    # ── 日程列表 ──────────────────────────

    def _load_events(self):
        if not self._calendar_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        calendar_id = self._get_selected_calendar_id()
        if not calendar_id:
            QMessageBox.warning(self, "提示", "请先加载并选择一个日历")
            return

        date = self.list_date_edit.date()
        start_dt = datetime(date.year(), date.month(), date.day(), 0, 0)
        end_dt = start_dt + timedelta(days=1)

        start_time = start_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")

        self.status_label.setText("正在加载日程...")
        self.load_events_btn.setEnabled(False)

        self._worker = ApiWorker(
            self._calendar_api.list_events,
            calendar_id, start_time, end_time,
        )
        self._worker.finished.connect(self._on_events_loaded)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_events_loaded(self, result):
        self.load_events_btn.setEnabled(True)
        events = result.get("data", {}).get("items", [])

        self.events_table.setRowCount(len(events))
        for r, event in enumerate(events):
            summary = event.get("summary", "(无标题)")
            event_id = event.get("event_id", "")

            # 时间可以是 timestamp 或 date 字段
            start_info = event.get("start_time", {})
            end_info = event.get("end_time", {})
            start_str = self._format_event_time(start_info)
            end_str = self._format_event_time(end_info)
            status = event.get("free_busy_status", "")

            self.events_table.setItem(r, 0, QTableWidgetItem(summary))
            self.events_table.setItem(r, 1, QTableWidgetItem(start_str))
            self.events_table.setItem(r, 2, QTableWidgetItem(end_str))
            self.events_table.setItem(r, 3, QTableWidgetItem(status))
            self.events_table.setItem(r, 4, QTableWidgetItem(event_id))

        self.status_label.setText(f"已加载 {len(events)} 条日程")

    def _format_event_time(self, time_info: dict) -> str:
        """格式化日程时间（支持 timestamp 和 date 两种格式）"""
        ts = time_info.get("timestamp", "")
        if ts:
            try:
                return time_mod.strftime("%H:%M", time_mod.localtime(int(ts)))
            except (ValueError, OSError):
                return ts
        date_str = time_info.get("date", "")
        if date_str:
            return f"全天({date_str})"
        return ""

    # ── 创建日程 ──────────────────────────

    def _create_event(self):
        if not self._calendar_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        summary = self.summary_input.text().strip()
        if not summary:
            QMessageBox.warning(self, "提示", "请输入日程标题")
            return

        calendar_id = self._get_selected_calendar_id()
        if not calendar_id:
            QMessageBox.warning(self, "提示", "请先加载并选择一个日历")
            return

        date = self.date_edit.date()
        start_time = self.start_time_edit.time()
        end_time = self.end_time_edit.time()

        # 构造时间戳（秒级）
        start_dt = datetime(date.year(), date.month(), date.day(),
                            start_time.hour(), start_time.minute())
        end_dt = datetime(date.year(), date.month(), date.day(),
                          end_time.hour(), end_time.minute())

        start_ts = str(int(start_dt.timestamp()))
        end_ts = str(int(end_dt.timestamp()))

        attendees_text = self.attendees_input.text().strip()
        attendee_ids = [a.strip() for a in attendees_text.split(",") if a.strip()] if attendees_text else []

        description = self.desc_input.text().strip()
        with_video = self.video_check.isChecked()

        self.status_label.setText("正在创建日程...")
        self.create_event_btn.setEnabled(False)

        self._worker = ApiWorker(
            self._calendar_api.create_event,
            summary, start_ts, end_ts, description,
            attendee_ids, with_video, calendar_id,
        )
        self._worker.finished.connect(self._on_event_created)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_event_created(self, result):
        self.create_event_btn.setEnabled(True)
        event = result.get("data", {}).get("event", {})
        event_id = event.get("event_id", "")
        self.status_label.setText(f"✅ 日程创建成功 (ID: {event_id})")
        QMessageBox.information(self, "成功", f"日程创建成功！\nEvent ID: {event_id}")

    # ── 空闲时段查询 ──────────────────────────

    def _find_free_slots(self):
        if not self._calendar_api:
            QMessageBox.warning(self, "提示", "请先完成认证")
            return

        users_text = self.freebusy_users_input.text().strip()
        if not users_text:
            QMessageBox.warning(self, "提示", "请输入用户 open_id")
            return

        user_ids = [u.strip() for u in users_text.split(",") if u.strip()]
        date = self.free_date_edit.date()
        date_str = f"{date.year()}-{date.month():02d}-{date.day():02d}"

        start_hour = self.start_hour_spin.value()
        end_hour = self.end_hour_spin.value()
        duration = self.duration_spin.value()

        self.status_label.setText("正在查找空闲时段...")
        self.find_free_btn.setEnabled(False)

        self._worker = ApiWorker(
            self._calendar_api.find_free_slots,
            user_ids, date_str, start_hour, end_hour, duration,
        )
        self._worker.finished.connect(self._on_free_slots_found)
        self._worker.error.connect(self._on_api_error)
        self._worker.start()

    def _on_free_slots_found(self, slots):
        self.find_free_btn.setEnabled(True)
        self.free_slots_table.setRowCount(len(slots))

        for r, slot in enumerate(slots):
            self.free_slots_table.setItem(r, 0, QTableWidgetItem(slot.get("start", "")))
            self.free_slots_table.setItem(r, 1, QTableWidgetItem(slot.get("end", "")))
            self.free_slots_table.setItem(r, 2, QTableWidgetItem(str(slot.get("duration", ""))))

        if slots:
            self.status_label.setText(f"找到 {len(slots)} 个空闲时段")
        else:
            self.status_label.setText("未找到空闲时段")

    # ── 错误处理 ──────────────────────────

    def _on_api_error(self, error_msg):
        self.create_event_btn.setEnabled(True)
        self.load_events_btn.setEnabled(True)
        self.load_calendars_btn.setEnabled(True)
        self.find_free_btn.setEnabled(True)
        self.status_label.setText(f"❌ 错误: {error_msg}")
        QMessageBox.critical(self, "API 错误", error_msg)
