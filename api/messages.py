"""飞书消息 API 封装"""

import json
from api.auth import FeishuAuth


class MessagesAPI:
    """消息相关接口"""

    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    def send_text_message(self, receive_id: str, text: str, receive_id_type: str = "open_id") -> dict:
        """
        发送文本消息

        :param receive_id: 接收者 ID (open_id / chat_id / user_id / union_id / email)
        :param text: 消息文本
        :param receive_id_type: ID 类型
        :return: API 响应数据
        """
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }
        return self.auth.request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json=payload,
        )

    def send_rich_text_message(self, receive_id: str, content: dict, receive_id_type: str = "open_id") -> dict:
        """
        发送富文本消息

        :param receive_id: 接收者 ID
        :param content: 富文本内容 (post 格式)
        :param receive_id_type: ID 类型
        :return: API 响应数据
        """
        payload = {
            "receive_id": receive_id,
            "msg_type": "post",
            "content": json.dumps(content),
        }
        return self.auth.request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json=payload,
        )

    def send_interactive_message(self, receive_id: str, card: dict, receive_id_type: str = "open_id") -> dict:
        """
        发送卡片消息

        :param receive_id: 接收者 ID
        :param card: 卡片内容
        :param receive_id_type: ID 类型
        :return: API 响应数据
        """
        payload = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card),
        }
        return self.auth.request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json=payload,
        )

    def get_chat_list(self, page_token: str = "") -> dict:
        """
        获取机器人所在的群列表

        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {"page_size": 50}
        if page_token:
            params["page_token"] = page_token

        return self.auth.request("GET", "/im/v1/chats", params=params)

    def get_all_chats(self) -> list[dict]:
        """获取所有群列表（自动分页）"""
        all_chats = []
        page_token = ""

        while True:
            data = self.get_chat_list(page_token)
            items = data.get("data", {}).get("items", [])
            all_chats.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token", "")

        return all_chats

    def get_chat_members(self, chat_id: str, page_token: str = "") -> dict:
        """
        获取群成员列表

        :param chat_id: 群 ID
        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {"page_size": 50}
        if page_token:
            params["page_token"] = page_token

        return self.auth.request("GET", f"/im/v1/chats/{chat_id}/members", params=params)

    def get_chat_messages(self, container_id: str, start_time: str = "", end_time: str = "",
                          page_token: str = "", page_size: int = 50, sort_type: str = "ByCreateTimeDesc") -> dict:
        """
        获取会话（群聊或单聊）的历史消息

        :param container_id: 会话 ID (chat_id)
        :param start_time: 起始时间戳（秒级），可选
        :param end_time: 结束时间戳（秒级），可选
        :param page_token: 分页 token
        :param page_size: 每页数量，最大50
        :param sort_type: 排序方式 ByCreateTimeAsc / ByCreateTimeDesc
        :return: API 响应数据
        """
        params = {
            "container_id_type": "chat",
            "container_id": container_id,
            "page_size": page_size,
            "sort_type": sort_type,
        }
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if page_token:
            params["page_token"] = page_token

        return self.auth.request("GET", "/im/v1/messages", params=params)

    def get_all_chat_messages(self, container_id: str, start_time: str = "", end_time: str = "",
                              max_count: int = 200) -> list[dict]:
        """
        获取会话的所有历史消息（自动分页，限制最大条数）

        :param container_id: 会话 ID (chat_id)
        :param start_time: 起始时间戳（秒级），可选
        :param end_time: 结束时间戳（秒级），可选
        :param max_count: 最大获取条数
        :return: 消息列表
        """
        all_messages = []
        page_token = ""

        while len(all_messages) < max_count:
            data = self.get_chat_messages(
                container_id, start_time, end_time, page_token,
                sort_type="ByCreateTimeAsc"
            )
            items = data.get("data", {}).get("items", [])
            all_messages.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token", "")

        return all_messages[:max_count]

    def get_chat_info(self, chat_id: str) -> dict:
        """
        获取群信息

        :param chat_id: 群 ID
        :return: API 响应数据
        """
        return self.auth.request("GET", f"/im/v1/chats/{chat_id}")

    def get_all_chat_members(self, chat_id: str) -> list[dict]:
        """
        获取群所有成员（自动分页）

        :param chat_id: 群 ID
        :return: 成员列表
        """
        all_members = []
        page_token = ""

        while True:
            data = self.get_chat_members(chat_id, page_token)
            items = data.get("data", {}).get("items", [])
            all_members.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token", "")

        return all_members

    def reply_message(self, message_id: str, msg_type: str, content: str) -> dict:
        """
        回复消息

        :param message_id: 要回复的消息 ID
        :param msg_type: 消息类型 (text / post / interactive)
        :param content: 消息内容（JSON 字符串）
        :return: API 响应数据
        """
        payload = {
            "msg_type": msg_type,
            "content": content,
        }
        return self.auth.request(
            "POST",
            f"/im/v1/messages/{message_id}/reply",
            json=payload,
        )


class CardBuilder:
    """飞书卡片消息构建器"""

    # 颜色模板
    TEMPLATES = [
        "blue", "turquoise", "green", "orange", "red",
        "purple", "indigo", "grey", "wathet", "yellow",
        "carmine", "violet",
    ]

    @staticmethod
    def build(
        title: str,
        template: str = "blue",
        content: str = None,
        fields: list[dict] = None,
        buttons: list[dict] = None,
        note: str = None,
        elements: list[dict] = None,
    ) -> dict:
        """
        构建卡片消息内容

        :param title: 卡片标题
        :param template: 头部颜色 (blue/green/orange/red/purple 等)
        :param content: 正文内容（支持 lark_md 语法）
        :param fields: 字段列表 [{"title": "标题", "value": "内容", "short": True}]
        :param buttons: 按钮列表 [{"text": "文本", "url": "链接", "type": "primary"}]
        :param note: 底部备注
        :param elements: 完全自定义元素列表（优先级最高）
        :return: 卡片内容字典
        """
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": template,
            },
            "elements": [],
        }

        # 完全自定义模式
        if elements:
            card["elements"] = elements
            return card

        # 正文
        if content:
            card["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": content},
            })

        # 字段
        if fields:
            field_elements = []
            for field in fields:
                field_elements.append({
                    "is_short": field.get("short", True),
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.get('title', '')}**\n{field.get('value', '')}",
                    },
                })
            # 每 2 个字段一组
            for i in range(0, len(field_elements), 2):
                card["elements"].append({
                    "tag": "div",
                    "fields": field_elements[i : i + 2],
                })

        # 分割线
        if (content or fields) and (buttons or note):
            card["elements"].append({"tag": "hr"})

        # 按钮
        if buttons:
            actions = []
            for btn in buttons:
                action = {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": btn.get("text", "按钮")},
                    "type": btn.get("type", "primary"),
                }
                if btn.get("url"):
                    action["url"] = btn["url"]
                if btn.get("value"):
                    action["value"] = btn["value"]
                actions.append(action)
            card["elements"].append({"tag": "action", "actions": actions})

        # 备注
        if note:
            card["elements"].append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": note}],
            })

        return card

    @staticmethod
    def build_with_images(
        title: str,
        template: str = "blue",
        content: str = None,
        images: list = None,
        fields: list[dict] = None,
        buttons: list[dict] = None,
        note: str = None,
    ) -> dict:
        """
        构建带图片的卡片

        :param title: 卡片标题
        :param template: 颜色模板
        :param content: 正文
        :param images: 图片列表 [{"image_key": "xxx", "alt": "描述"}] 或 ["image_key"]
        :param fields: 字段列表
        :param buttons: 按钮列表
        :param note: 备注
        :return: 卡片内容字典
        """
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": template,
            },
            "elements": [],
        }

        if content:
            card["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": content},
            })

        if images:
            for img in images:
                if isinstance(img, str):
                    img_key, alt_text = img, "图片"
                else:
                    img_key = img.get("image_key")
                    alt_text = img.get("alt", "图片")
                card["elements"].append({
                    "tag": "img",
                    "img_key": img_key,
                    "alt": {"tag": "plain_text", "content": alt_text},
                })

        if fields:
            field_elements = []
            for field in fields:
                field_elements.append({
                    "is_short": field.get("short", True),
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{field.get('title', '')}**\n{field.get('value', '')}",
                    },
                })
            for i in range(0, len(field_elements), 2):
                card["elements"].append({
                    "tag": "div",
                    "fields": field_elements[i : i + 2],
                })

        if (content or images or fields) and (buttons or note):
            card["elements"].append({"tag": "hr"})

        if buttons:
            actions = []
            for btn in buttons:
                action = {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": btn.get("text", "按钮")},
                    "type": btn.get("type", "primary"),
                }
                if btn.get("url"):
                    action["url"] = btn["url"]
                actions.append(action)
            card["elements"].append({"tag": "action", "actions": actions})

        if note:
            card["elements"].append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": note}],
            })

        return card
