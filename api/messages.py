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
