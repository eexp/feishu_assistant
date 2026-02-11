"""飞书日历 (Calendar) API 封装"""

from datetime import datetime, timezone, timedelta
from api.auth import FeishuAuth


class CalendarAPI:
    """日历相关接口"""

    def __init__(self, auth: FeishuAuth):
        self.auth = auth
        self._calendar_id: str | None = None

    # ── 日历管理 ──────────────────────────

    def list_calendars(self, page_size: int = 500, page_token: str = "") -> dict:
        """
        获取日历列表（分页查询当前身份的日历）

        :param page_size: 每页数量（50-1000），默认 500
        :param page_token: 分页 token，首次请求不填
        :return: API 响应数据，含 calendar_list、has_more、page_token、sync_token
        """
        params = {"page_size": max(50, min(page_size, 1000))}
        if page_token:
            params["page_token"] = page_token
        return self.auth.request("GET", "/calendar/v4/calendars", params=params)

    def get_all_calendars(self) -> list[dict]:
        """
        获取所有日历（自动分页）

        :return: 日历列表
        """
        all_calendars = []
        page_token = ""

        while True:
            data = self.list_calendars(page_token=page_token)
            items = data.get("data", {}).get("calendar_list", [])
            all_calendars.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token", "")
            if not page_token:
                break

        return all_calendars

    def get_primary_calendar_id(self) -> str:
        """获取主日历 ID"""
        if self._calendar_id:
            return self._calendar_id

        calendars = self.get_all_calendars()
        for cal in calendars:
            if cal.get("type") == "primary":
                self._calendar_id = cal["calendar_id"]
                return self._calendar_id

        raise Exception("找不到主日历")

    # ── 日程管理 ──────────────────────────

    def list_events(
        self,
        calendar_id: str = "",
        start_time: str = "",
        end_time: str = "",
        page_token: str = "",
        page_size: int = 50,
    ) -> dict:
        """
        获取日程列表

        :param calendar_id: 日历 ID，空则使用主日历
        :param start_time: 起始时间 (RFC 3339 格式，如 2024-01-01T00:00:00+08:00)
        :param end_time: 结束时间
        :param page_token: 分页 token
        :param page_size: 每页数量
        :return: API 响应数据
        """
        if not calendar_id:
            calendar_id = self.get_primary_calendar_id()

        params = {"page_size": page_size}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if page_token:
            params["page_token"] = page_token

        return self.auth.request(
            "GET",
            f"/calendar/v4/calendars/{calendar_id}/events",
            params=params,
        )

    def get_event(self, event_id: str, calendar_id: str = "") -> dict:
        """
        获取单个日程详情

        :param event_id: 日程 ID
        :param calendar_id: 日历 ID
        :return: API 响应数据
        """
        if not calendar_id:
            calendar_id = self.get_primary_calendar_id()

        return self.auth.request(
            "GET",
            f"/calendar/v4/calendars/{calendar_id}/events/{event_id}",
        )

    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        attendee_ids: list[str] = None,
        with_video: bool = False,
        calendar_id: str = "",
    ) -> dict:
        """
        创建日程/会议

        :param summary: 日程标题
        :param start_time: 开始时间戳（秒级字符串）
        :param end_time: 结束时间戳（秒级字符串）
        :param description: 描述
        :param attendee_ids: 参会人 open_id 列表
        :param with_video: 是否创建视频会议
        :param calendar_id: 日历 ID
        :return: API 响应数据
        """
        if not calendar_id:
            calendar_id = self.get_primary_calendar_id()

        event_data = {
            "summary": summary,
            "description": description,
            "need_notification": True,
            "start_time": {"timestamp": str(start_time)},
            "end_time": {"timestamp": str(end_time)},
            "visibility": "default",
            "attendee_ability": "can_modify_event",
            "free_busy_status": "busy",
        }

        if with_video:
            event_data["vchat"] = {"vc_type": "vc"}

        result = self.auth.request(
            "POST",
            f"/calendar/v4/calendars/{calendar_id}/events",
            json=event_data,
            params={"user_id_type": "open_id"},
        )

        # 添加参会人
        if attendee_ids and result.get("data", {}).get("event", {}).get("event_id"):
            event_id = result["data"]["event"]["event_id"]
            try:
                self.add_attendees(calendar_id, event_id, attendee_ids)
            except Exception:
                pass  # 参会人添加失败不影响日程创建

        return result

    def update_event(self, event_id: str, calendar_id: str = "", **kwargs) -> dict:
        """
        更新日程

        :param event_id: 日程 ID
        :param calendar_id: 日历 ID
        :param kwargs: 要更新的字段
        :return: API 响应数据
        """
        if not calendar_id:
            calendar_id = self.get_primary_calendar_id()

        return self.auth.request(
            "PATCH",
            f"/calendar/v4/calendars/{calendar_id}/events/{event_id}",
            json=kwargs,
        )

    def delete_event(self, event_id: str, calendar_id: str = "") -> dict:
        """
        删除日程

        :param event_id: 日程 ID
        :param calendar_id: 日历 ID
        :return: API 响应数据
        """
        if not calendar_id:
            calendar_id = self.get_primary_calendar_id()

        return self.auth.request(
            "DELETE",
            f"/calendar/v4/calendars/{calendar_id}/events/{event_id}",
        )

    # ── 参会人管理 ──────────────────────────

    def add_attendees(
        self, calendar_id: str, event_id: str, user_ids: list[str]
    ) -> dict:
        """
        添加参会人

        :param calendar_id: 日历 ID
        :param event_id: 日程 ID
        :param user_ids: 用户 open_id 列表
        :return: API 响应数据
        """
        payload = {
            "attendees": [{"type": "user", "user_id": uid} for uid in user_ids],
            "need_notification": True,
        }
        return self.auth.request(
            "POST",
            f"/calendar/v4/calendars/{calendar_id}/events/{event_id}/attendees",
            json=payload,
            params={"user_id_type": "open_id"},
        )

    def list_attendees(self, event_id: str, calendar_id: str = "") -> dict:
        """
        获取参会人列表

        :param event_id: 日程 ID
        :param calendar_id: 日历 ID
        :return: API 响应数据
        """
        if not calendar_id:
            calendar_id = self.get_primary_calendar_id()

        return self.auth.request(
            "GET",
            f"/calendar/v4/calendars/{calendar_id}/events/{event_id}/attendees",
            params={"user_id_type": "open_id"},
        )

    # ── 忙闲查询 ──────────────────────────

    def get_freebusy(self, user_id: str, time_min: str, time_max: str) -> dict:
        """
        查询用户忙闲状态

        :param user_id: 用户 open_id
        :param time_min: 起始时间 (RFC 3339)
        :param time_max: 结束时间 (RFC 3339)
        :return: API 响应数据
        """
        payload = {
            "time_min": time_min,
            "time_max": time_max,
            "user_id": user_id,
        }
        return self.auth.request(
            "POST",
            "/calendar/v4/freebusy/list",
            json=payload,
            params={"user_id_type": "open_id"},
        )

    def find_free_slots(
        self,
        user_ids: list[str],
        date: str,
        start_hour: int = 9,
        end_hour: int = 18,
        duration_minutes: int = 30,
    ) -> list[dict]:
        """
        查找多个用户的共同空闲时段

        :param user_ids: 用户 open_id 列表
        :param date: 日期，如 "2024-01-15"
        :param start_hour: 起始小时 (24h)
        :param end_hour: 结束小时 (24h)
        :param duration_minutes: 所需空闲时长（分钟）
        :return: 空闲时段列表
        """
        time_min = f"{date}T{start_hour:02d}:00:00+08:00"
        time_max = f"{date}T{end_hour:02d}:00:00+08:00"

        all_busy = []
        for user_id in user_ids:
            try:
                result = self.get_freebusy(user_id, time_min, time_max)
                for item in result.get("data", {}).get("freebusy_list", []):
                    all_busy.append((item["start_time"], item["end_time"]))
            except Exception:
                pass

        def _time_to_minutes(t: str) -> int:
            return int(t[11:13]) * 60 + int(t[14:16])

        busy_intervals = sorted(
            [(_time_to_minutes(s), _time_to_minutes(e)) for s, e in all_busy]
        )

        # 合并重叠区间
        merged = []
        for start, end in busy_intervals:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # 计算空闲时段
        free_slots = []
        current = start_hour * 60
        end_minutes = end_hour * 60

        for busy_start, busy_end in merged:
            if current < busy_start:
                gap = busy_start - current
                if gap >= duration_minutes:
                    free_slots.append({
                        "start": f"{current // 60:02d}:{current % 60:02d}",
                        "end": f"{busy_start // 60:02d}:{busy_start % 60:02d}",
                        "duration": gap,
                    })
            current = max(current, busy_end)

        if current < end_minutes:
            gap = end_minutes - current
            if gap >= duration_minutes:
                free_slots.append({
                    "start": f"{current // 60:02d}:{current % 60:02d}",
                    "end": f"{end_minutes // 60:02d}:{end_minutes % 60:02d}",
                    "duration": gap,
                })

        return free_slots
