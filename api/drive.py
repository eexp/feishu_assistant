"""飞书云盘 (Drive) API 封装 —— 文件夹管理与权限管理"""

from api.auth import FeishuAuth


class DriveAPI:
    """云盘（文件夹 + 权限）相关接口"""

    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    # ── 文件夹管理 ──────────────────────────

    def get_root_folder_meta(self) -> dict:
        """
        获取「我的空间」根文件夹元信息

        :return: API 响应数据（含 token）
        """
        return self.auth.request("GET", "/drive/explorer/v2/root_folder/meta")

    def get_root_folder_token(self) -> str:
        """返回根文件夹 token"""
        data = self.get_root_folder_meta()
        return data.get("data", {}).get("token", "")

    def create_folder(self, name: str, parent_token: str = "") -> dict:
        """
        创建文件夹

        :param name: 文件夹名称
        :param parent_token: 父文件夹 token，空则在根目录
        :return: API 响应数据
        """
        if not parent_token:
            parent_token = self.get_root_folder_token()

        payload = {
            "name": name,
            "folder_token": parent_token,
        }
        return self.auth.request("POST", "/drive/v1/files/create_folder", json=payload)

    def list_files(self, folder_token: str = "", page_token: str = "", page_size: int = 50) -> dict:
        """
        列出文件夹中的文件

        :param folder_token: 文件夹 token，空表示根目录
        :param page_token: 分页 token
        :param page_size: 每页数量
        :return: API 响应数据
        """
        params = {"page_size": page_size}
        if folder_token:
            params["folder_token"] = folder_token
        if page_token:
            params["page_token"] = page_token
        return self.auth.request("GET", "/drive/v1/files", params=params)

    def move_file(self, file_token: str, dst_folder_token: str, file_type: str = "file") -> dict:
        """
        移动文件/文件夹到指定位置

        :param file_token: 文件 token
        :param dst_folder_token: 目标文件夹 token
        :param file_type: 类型 (file / folder)
        :return: API 响应数据
        """
        payload = {"type": file_type, "folder_token": dst_folder_token}
        return self.auth.request(
            "POST", f"/drive/v1/files/{file_token}/move", json=payload
        )

    def delete_file(self, file_token: str, file_type: str = "file") -> dict:
        """
        删除文件/文件夹

        :param file_token: 文件 token
        :param file_type: 类型 (file / docx / sheet / bitable / folder)
        :return: API 响应数据
        """
        return self.auth.request(
            "DELETE",
            f"/drive/v1/files/{file_token}",
            params={"type": file_type},
        )

    # ── 权限管理 ──────────────────────────

    def get_permission_members(self, token: str, doc_type: str) -> dict:
        """
        获取文档/文件夹的协作者列表

        :param token: 文档/文件夹 token
        :param doc_type: 类型 (doc, docx, sheet, bitable, folder 等)
        :return: API 响应数据
        """
        return self.auth.request(
            "GET",
            f"/drive/v1/permissions/{token}/members",
            params={"type": doc_type},
        )

    def add_permission(
        self,
        token: str,
        doc_type: str,
        member_id: str,
        member_type: str = "openid",
        perm: str = "view",
        notify: bool = True,
    ) -> dict:
        """
        为文档/文件夹添加协作者权限

        :param token: 文档/文件夹 token
        :param doc_type: 类型 (docx, sheet, bitable, folder)
        :param member_id: 成员 ID (open_id / user_id / email / chat_id)
        :param member_type: 成员类型 (openid, userid, email, openchat, opendepartmentid)
        :param perm: 权限级别 (view, edit, full_access)
        :param notify: 是否发送通知
        :return: API 响应数据
        """
        payload = {
            "member_type": member_type,
            "member_id": member_id,
            "perm": perm,
        }
        params = {
            "type": doc_type,
            "need_notification": "true" if notify else "false",
        }
        return self.auth.request(
            "POST",
            f"/drive/v1/permissions/{token}/members",
            json=payload,
            params=params,
        )

    def remove_permission(
        self,
        token: str,
        doc_type: str,
        member_id: str,
        member_type: str = "openid",
    ) -> dict:
        """
        移除协作者权限

        :param token: 文档/文件夹 token
        :param doc_type: 类型
        :param member_id: 成员 ID
        :param member_type: 成员类型
        :return: API 响应数据
        """
        params = {"type": doc_type, "member_type": member_type}
        return self.auth.request(
            "DELETE",
            f"/drive/v1/permissions/{token}/members/{member_id}",
            params=params,
        )

    def update_permission(
        self,
        token: str,
        doc_type: str,
        member_id: str,
        member_type: str = "openid",
        perm: str = "view",
    ) -> dict:
        """
        更新协作者权限

        :param token: 文档/文件夹 token
        :param doc_type: 类型
        :param member_id: 成员 ID
        :param member_type: 成员类型
        :param perm: 新权限级别
        :return: API 响应数据
        """
        payload = {"member_type": member_type, "perm": perm}
        params = {"type": doc_type}
        return self.auth.request(
            "PUT",
            f"/drive/v1/permissions/{token}/members/{member_id}",
            json=payload,
            params=params,
        )

    def batch_add_permissions(
        self,
        token: str,
        doc_type: str,
        member_ids: list[str],
        member_type: str = "openid",
        perm: str = "view",
    ) -> list[dict]:
        """
        批量添加权限（逐个调用）

        :param token: 文档/文件夹 token
        :param doc_type: 类型
        :param member_ids: 成员 ID 列表
        :param member_type: 成员类型
        :param perm: 权限级别
        :return: 结果列表
        """
        results = []
        for mid in member_ids:
            try:
                result = self.add_permission(
                    token, doc_type, mid,
                    member_type=member_type, perm=perm, notify=False,
                )
                results.append({"member_id": mid, "success": True, "data": result})
            except Exception as e:
                results.append({"member_id": mid, "success": False, "error": str(e)})
        return results

    def get_public_settings(self, token: str, doc_type: str) -> dict:
        """
        获取文档公共设置（谁可以查看/评论/编辑等）

        :param token: 文档 token
        :param doc_type: 类型
        :return: API 响应数据
        """
        return self.auth.request(
            "GET",
            f"/drive/v1/permissions/{token}/public",
            params={"type": doc_type},
        )

    def update_public_settings(self, token: str, doc_type: str, settings: dict) -> dict:
        """
        更新文档公共设置

        :param token: 文档 token
        :param doc_type: 类型
        :param settings: 设置字典，如 {"external_access": True, "link_share_entity": "anyone_readable"}
        :return: API 响应数据
        """
        return self.auth.request(
            "PATCH",
            f"/drive/v1/permissions/{token}/public",
            json=settings,
            params={"type": doc_type},
        )
