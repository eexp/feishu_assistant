"""飞书联系人 API 封装"""

from api.auth import FeishuAuth


class ContactsAPI:
    """联系人相关接口"""

    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    def get_departments(self, parent_department_id: str = "0", page_token: str = "") -> dict:
        """
        获取子部门列表

        :param parent_department_id: 父部门 ID，根部门为 "0"
        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {
            "department_id_type": "department_id",
            "page_size": 50,
        }
        if page_token:
            params["page_token"] = page_token

        return self.auth.request(
            "GET",
            f"/contact/v3/departments/{parent_department_id}/children",
            params=params,
        )

    def get_all_departments(self, parent_department_id: str = "0") -> list[dict]:
        """递归获取所有子部门（包括嵌套子部门）"""
        all_departments = []
        self._recursive_get_departments(parent_department_id, all_departments)
        return all_departments

    def _recursive_get_departments(self, parent_id: str, result: list[dict]):
        """递归获取所有层级的部门"""
        page_token = ""
        while True:
            data = self.get_departments(parent_id, page_token)
            items = data.get("data", {}).get("items", [])

            for dept in items:
                result.append(dept)
                # 递归获取子部门
                dept_id = dept.get("department_id", "")
                if dept_id:
                    self._recursive_get_departments(dept_id, result)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token", "")

    def get_department_users(self, department_id: str, page_token: str = "") -> dict:
        """
        获取部门下的用户列表

        :param department_id: 部门 ID
        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {
            "department_id_type": "department_id",
            "department_id": department_id,
            "page_size": 50,
        }
        if page_token:
            params["page_token"] = page_token

        return self.auth.request(
            "GET",
            "/contact/v3/users/find_by_department",
            params=params,
        )

    def get_all_department_users(self, department_id: str) -> list[dict]:
        """获取部门下所有用户（自动分页）"""
        all_users = []
        page_token = ""

        while True:
            data = self.get_department_users(department_id, page_token)
            items = data.get("data", {}).get("items", [])
            all_users.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token", "")

        return all_users

    def search_user(self, query: str, page_token: str = "") -> dict:
        """
        搜索用户

        :param query: 搜索关键词
        :param page_token: 分页 token
        :return: API 响应数据
        """
        params = {
            "page_size": 20,
        }
        if page_token:
            params["page_token"] = page_token

        return self.auth.request(
            "POST",
            "/search/v1/user",
            params=params,
            json={"query": query},
        )

    def get_user_info(self, user_id: str, user_id_type: str = "open_id") -> dict:
        """
        获取单个用户详细信息

        :param user_id: 用户 ID
        :param user_id_type: ID 类型 (open_id, union_id, user_id)
        :return: API 响应数据
        """
        params = {"user_id_type": user_id_type}
        return self.auth.request("GET", f"/contact/v3/users/{user_id}", params=params)

    def batch_get_user_by_id(self, emails: list[str] = None, mobiles: list[str] = None) -> dict:
        """
        通过邮箱或手机号批量获取用户 ID

        :param emails: 邮箱列表
        :param mobiles: 手机号列表
        :return: API 响应数据
        """
        payload = {}
        if emails:
            payload["emails"] = emails
        if mobiles:
            payload["mobiles"] = mobiles

        return self.auth.request(
            "POST",
            "/contact/v3/users/batch_get_id",
            params={"user_id_type": "open_id"},
            json=payload,
        )
