"""飞书认证模块：管理 tenant_access_token 的获取和刷新"""

import time
import requests


class FeishuAuth:
    """飞书 API 认证管理器"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None
        self._token_expire: float = 0  # token 过期的时间戳

    def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token，带缓存，过期前自动刷新"""
        # 提前 5 分钟刷新 token
        if self._token and time.time() < self._token_expire - 300:
            return self._token

        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data.get('msg', '未知错误')}")

        self._token = data["tenant_access_token"]
        # expire 单位是秒
        self._token_expire = time.time() + data.get("expire", 7200)
        return self._token

    def request(self, method: str, path: str, **kwargs) -> dict:
        """
        统一请求方法，自动携带 Authorization 头。

        :param method: HTTP 方法 (GET, POST, PUT, DELETE, PATCH)
        :param path: API 路径，如 /contact/v3/departments
        :param kwargs: 传给 requests 的额外参数 (params, json, data 等)
        :return: 响应 JSON 字典
        """
        token = self.get_tenant_access_token()
        url = f"{self.BASE_URL}{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        resp = requests.request(method, url, headers=headers, timeout=15, **kwargs)

        # 尝试解析响应体，即使 HTTP 状态码非 200
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            raise Exception(f"无法解析响应: {resp.text[:500]}")

        # 飞书 API 统一错误码检查
        code = data.get("code")
        if code is not None and code != 0:
            raise Exception(f"API 错误 [{code}]: {data.get('msg', '未知错误')}")

        # 如果没有 code 字段但 HTTP 状态码异常
        if not resp.ok and code is None:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:500]}")

        return data

    def get_bot_info(self) -> dict:
        """
        获取机器人信息，包括应用名称、头像等。
        
        :return: 机器人信息字典，包含 app_name, avatar_url, open_id 等
        """
        data = self.request("GET", "/bot/v3/info")
        return data.get("bot", {})

    def verify(self) -> bool:
        """验证凭证是否有效，成功返回 True"""
        try:
            self.get_tenant_access_token()
            return True
        except Exception:
            return False
